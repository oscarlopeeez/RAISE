# Informe detallado del proyecto IRRBB (RAISE)

Este README contiene un informe técnico detallado del proyecto, archivo por archivo, describiendo su propósito, cómo funciona cada componente, las funciones principales y observaciones críticas para redacción de informes o mejoras. Está en español.

## Resumen del propósito

La aplicación calcula métricas IRRBB: EVE (Economic Value of Equity) y NII (Net Interest Income) para contratos bancarios. Los contratos se cargan por Excel, se generan flujos de caja, se construyen curvas de tasas con shocks predefinidos y se calculan métricas por escenario. Los resultados se guardan en la base de datos y pueden exportarse a una plantilla J_03.

## Estructura general

- [myFirstServer/settings.py](myFirstServer/settings.py) — configuraciones del proyecto.
- [myFirstServer/urls.py](myFirstServer/urls.py) — URLs raíz.
- [irrbb_app/] — aplicación principal que contiene modelos, vistas, servicios y plantillas.
  - [irrbb_app/models.py](irrbb_app/models.py)
  - [irrbb_app/views.py](irrbb_app/views.py)
  - [irrbb_app/forms.py](irrbb_app/forms.py)
  - [irrbb_app/admin.py](irrbb_app/admin.py)
  - [irrbb_app/urls.py](irrbb_app/urls.py)
  - templates: [templates/irrbb_app/*](templates/irrbb_app)
  - services: [irrbb_app/services/*](irrbb_app/services)
- [users/] — app de usuarios con `CustomUser`, APIs y formularios.
  - [users/models.py](users/models.py)
  - [users/views.py](users/views.py)
  - [users/serializers.py](users/serializers.py)
  - [users/forms.py](users/forms.py)
  - [users/admin.py](users/admin.py)

## Puntos clave de arquitectura

- Modelo de datos: `Banco`, `Contrato`, `ResultadoBalance` en `irrbb_app/models.py`.
- Flujo principal:
  1. El usuario sube un Excel con contratos (`irrbb_app/views.UploadContractsView`).
  2. `import_excel` valida y crea instancias de `Contrato`.
  3. `contract_pricing.run_balance_pricing` orquesta la creación de flujos (`cashflows.build_cashflows`), construcción de curvas (`curve.build_default_curve`), cálculo de EVE (`eve_calculation.calculate_eve`) y NII (`nii_calculation.calculate_nii`), agregación y persistencia en `ResultadoBalance`.
  4. Resultados accesibles desde interfaz y exportables con `export_j03.export_excel`.

---

## Explicación detallada por archivo

A continuación se describe cada archivo con funciones y responsabilidades.

### `myFirstServer/settings.py`
- Define `BASE_DIR`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`.
- `INSTALLED_APPS` incluye `rest_framework`, `users`, `irrbb_app`.
- `DATABASES`: SQLite (`db.sqlite3`).
- `AUTH_USER_MODEL = "users.CustomUser"` apunta a usuario personalizado.
- Plantillas y paths para estáticos, login/logout.

Uso en el sistema: controla entorno y dependencias básicas; para producción debe ajustarse `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS`.

### `myFirstServer/urls.py` y `irrbb_app/urls.py`
- `myFirstServer/urls.py`: incluye `admin/`, rutas de auth (`login`, `logout`, `register`) y las apps `users` y `irrbb_app`.
- `irrbb_app/urls.py`: mapea rutas principales: inicio, `dashboard`, `upload`, `resultados/` y `download_template`.

Esto define la navegación principal de la aplicación.

### `irrbb_app/models.py`
- `Banco`: nombre único, `created_at`.
- `Contrato`: representa un contrato financiero con campos:
  - `banco` (FK), `numero_contrato`, `producto`, `activo_pasivo` (`ACTIVO`/`PASIVO`), `nominal`, `fecha_inicio`, `fecha_vencimiento`, `tipo_interes` (`FIJO`/`VARIABLE`), `tipo_amortizacion` (`FRANCESA`/`ALEMANA`/`BULLET`), `cupon_spread`, `curva_asociada`, `frecuencia_cupon`.
- `ResultadoBalance`: guarda resultados por banco y cálculo, incluyendo EVE y NII por escenarios y `metadata` JSON.

Importancia: `Contrato` y `ResultadoBalance` son el corazón del modelo, permiten trazabilidad y persistencia de cálculos.

### `irrbb_app/admin.py`
- Registran `Banco`, `Contrato` y `ResultadoBalance` con campos útiles para filtrado y búsqueda.

### `irrbb_app/forms.py`
- `UploadContractsForm` con `id_empleado` y `excel_file`.
- Se usa en `UploadContractsView` para recibir fichero y vincularlo a un usuario.

### `irrbb_app/views.py` (comportamiento y flujos)
- `DashboardView`: recoge `latest_results`, contadores de bancos y contratos.
- `UploadContractsView`:
  - Valida `id_empleado` (busca `CustomUser` por id).
  - Verifica que el usuario tenga `bank_name` asociado.
  - Llama `import_excel.validate_contracts_excel` para validar el Excel.
  - Si OK, llama `import_excel.load_contracts_from_excel` para crear `Contrato` por fila.
  - Ejecuta `contract_pricing.run_balance_pricing(banco, uploaded_by)` para calcular y persistir `ResultadoBalance`.
- `ResultsHistoryView`: lista `ResultadoBalance` filtrado por banco del usuario.
- `DetailView`: muestra detalle y permite `?download=excel` para exportar J_03 (recalcula `activos/pasivos` al vuelo usando `_process_contracts`).
- `download_template`: genera un `Workbook` con ejemplo de columnas y lo retorna para descarga.

Notas operativas: `UploadContractsView` emite `messages` con errores/éxitos y redirige al `dashboard`.

### `irrbb_app/templates/irrbb_app/*`
- `base.html`: layout global, menú condicional, estilos inline, muestra `messages`.
- `dashboard.html`, `results.html`, `detail.html`: muestran datos extraídos de las vistas.
- `upload.html`, `login.html`, `register.html`, `start.html`: formularios y UI para interacción.

UI: sencilla, estilo oscuro, responsive básico con CSS inline.

### `irrbb_app/services/utils.py`
Funciones auxiliares:
- `tenor_to_years(tenor)`: convierte tenor (ej. `6M`, `1Y`) a años (6M→0.5). Lanza `ValueError` si unidad desconocida.
- `normalize_curve_points(plazos, tipos)`: aplica `tenor_to_years` y devuelve arrays (maturities, rates).
- `year_fraction_30_360(fecha_inicio, fecha_fin)`: convención 30/360.
- `interpolate_rate(curve_df, column, year_value)`: interpola linealmente con `np.interp`.

Observación: asegúrese de pasar siempre las columnas en la unidad esperada (bp o decimal según la función consumidora).

### `irrbb_app/services/curve.py`
- `EUR_SHOCKS_BP`: shocks en puntos base.
- `Curve`:
  - Toma `df_flatcurve` (tasas en decimal en `rate_flat_curve`).
  - Calcula `rate_base_curve = rate_flat_curve * 10000` (convierte a bp).
  - Genera escenarios:
    - Parallel up/down (± S_parallel).
    - Short up/down usando `short_shock = S_short * exp(-maturity/4)`.
    - Steepener/Flattener combinando short y long shocks.
- `build_default_curve()`: crea curva por defecto con plazos y tasas, devuelve DataFrame con columnas de escenario (en bp).

Importante: las columnas de salida están en puntos base (bp). Otras funciones deben dividir por 10000 antes de usar.

### `irrbb_app/services/cashflows.py`
- `generate_payment_dates(fecha_inicio, fecha_vencimiento, frecuencia_cupon)`: genera fechas de pago sumando meses por periodo.
- `effective_rate(contract, curve_df)`: devuelve tasa efectiva anual:
  - Si `FIJO` devuelve `contract.cupon_spread`.
  - Si `VARIABLE` interpola base de curva (`rate_base_curve` en bp) y divide por 10000; suma `cupon_spread`.
- `build_cashflows(contract, curve_df, valuation_date=None)`:
  - Calcula `payment_dates`, `n_periods`, `period_rate = effective_rate(...) / freq`.
  - Determina `sign` según `activo_pasivo`.
  - Soporta amortizaciones `FRANCESA` (cuota fija), `ALEMANA` (amortización fija), `BULLET`.
  - Por cada periodo genera fila con: `contract_id`, `payment_date`, `period_start`, `period_end`, `year_fraction` (30/360), `year` (t para descuento calculado como `max(0, dias)/360`), `rest_start`, `interest`, `principal`, `cashflow`, `rate_per_period`, `is_floating`, `activo_pasivo`.

Notas: `cupon_spread` debe estar en la misma unidad que `base_rate` (ambos como decimal) para que `effective_rate` sea correcto; revisar normalización al importar.

### `irrbb_app/services/eve_calculation.py`
- `SCENARIO_COLUMNS`: mapeo entre nombres de escenario EVE y columnas en `curve_df`.
- `discount_cashflows(cashflows_df, curve_df, curve_column)`:
  - Interpola `rates` (divide por 10000 para pasar de bp a decimal).
  - Calcula `pv = cashflow / (1 + rate) ** year`.
- `calculate_eve(cashflows_df, curve_df)`:
  - Itera escenarios en `SCENARIO_COLUMNS`, aplica `discount_cashflows` y suma `pv` para cada escenario.

Resultado: diccionario con EVE total por escenario.

### `irrbb_app/services/nii_calculation.py`
- `SCENARIO_COLUMNS`: para NII.
- `calculate_nii(cashflows_df, curve_df, horizon_years=1.0)`:
  - Filtra flujos con `year <= horizon_years`.
  - Interpola `base_rate` y `scenario_rate` (divide bp/10000).
  - `r = scenario_rate - base_rate`.
  - `repricing = rest_start * r * year_fraction * is_floating` (solo contratos flotantes).
  - `total_interest = interest + repricing`; suma por escenario.

Resultado: impacto sobre NII en el horizonte.

### `irrbb_app/services/import_excel.py`
- `validate_contracts_excel(archivo)`:
  - Lee archivo con pandas, normaliza columnas a minúsculas.
  - Valida presencia de columnas requeridas y consistencia por fila (tipos, rangos, fechas).
  - Devuelve `(ok_bool, errors_list)`.
- `load_contracts_from_excel(archivo, banco, curva="EURIBOR")`:
  - Lee Excel y por fila crea `Contrato` y `save()`.
  - Devuelve cantidad de filas importadas.

Recomendación: normalizar `cupon_spread` (p.ej. interpretar `5.0` como 5% o 0.05 según convención) y envolver creación en transacción para evitar importaciones parciales.

### `irrbb_app/services/export_j03.py`
- Define mapas `SCENARIOS`, `PRODUCTS_ACTIVOS`, `PRODUCTS_PASIVOS` con códigos y posiciones en plantilla.
- `export_excel(fecha, activos, pasivos, banco_name)`:
  - Carga `template.xlsx` con `openpyxl`, escribe encabezados y valores por producto (usa `abs(valor)`).
  - Devuelve `HttpResponse` con archivo para descargar.

Dependencia: `template.xlsx` debe existir en la raíz del proyecto.

### `irrbb_app/services/contract_pricing.py`
- Orquesta el proceso completo:
  - `_process_contracts`: genera cashflows por contrato, agrupa por `producto` en `activos`/`pasivos`.
  - `_calculate_eve_nii`: concatena flujos por grupo, llama a `calculate_eve` y `calculate_nii`, guarda en `productos_dict[producto]['scenario']`.
  - `_aggregate_results`: suma escenario por escenario para activos y pasivos.
  - `run_balance_pricing(banco, uploaded_by)`: función pública (decorada con `@transaction.atomic`) que construye curva por defecto, procesa contratos, agrega resultados y crea `ResultadoBalance` en BD.

Observación: `run_balance_pricing` asegura atomicidad al crear `ResultadoBalance`, pero la importación de contratos (antes) no está envuelta por defecto.

### App `users`
- `users/models.py`: `CustomUser(AbstractUser)` con campo adicional `bank_name` (FK a `irrbb_app.Banco`).
- `users/forms.py`: `CustomUserCreationForm` añade `bank_name` en registro web.
- `users/serializers.py`: `UserSerializer`, `BankSerializer`, `ChangePasswordSerializer` para API.
- `users/views.py`: APIs DRF para registro (devuelve tokens JWT), listado/gestion de usuarios (admin), perfil de usuario y cambio de contraseña; `SignupPageView` para registro web.
- `users/admin.py`: extiende `UserAdmin` para incluir `bank_name`.

---

## Observaciones críticas y sugerencias de mejora (prioritizadas)

1. Normalizar `cupon_spread` en `import_excel` (convertir porcentajes a decimal, p.ej. `5.0` → `0.05` o documentar formato esperado). Evita errores silenciosos.
2. Hacer atómica la importación de Excel (`load_contracts_from_excel`) para evitar estados parciales si falla a mitad.
3. Añadir tests unitarios para `cashflows.build_cashflows`, `eve_calculation.calculate_eve` y `nii_calculation.calculate_nii` con casos controlados.
4. Documentar claramente las unidades (decimal vs bp) en la top de `services/curve.py` y `README` y/o mantener tasas en decimal en todo el pipeline.
5. Manejo de errores y logs: agregar logging en `contract_pricing.run_balance_pricing` para auditoría.
6. Validaciones adicionales: verificar `frecuencia_cupon > 0`, fechas válidas y que `nominal >= 0` antes de construir flujos.

---

## ¿Qué más quieres que haga?
- Puedo generar este mismo informe con referencias línea a línea (añadiendo números de línea exactos) para cada función.
- Puedo implementar las mejoras: normalización de `cupon_spread` en `import_excel`, envolver import en transacción, y crear tests básicos.
- Puedo crear un fichero `requirements.txt` y un `Makefile`/README de ejecución.

Indica la siguiente acción que deseas (por ejemplo: "Añadir normalización y transacción en `import_excel` y crear tests").
