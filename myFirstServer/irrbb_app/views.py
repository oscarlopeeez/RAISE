from datetime import date
from django.http import HttpResponse, Http404
from openpyxl import Workbook
import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, TemplateView

from users.models import CustomUser

from .forms import UploadContractsForm
from .models import Banco, Contrato, ResultadoBalance
from .services import contract_pricing, import_excel
from .services.cashflows import build_cashflows
from .services.curve import build_default_curve
from .services.eve_calculation import calculate_eve
from .services.nii_calculation import calculate_nii
from .services.export_j03 import export_excel


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "irrbb_app/dashboard.html"

    def get_context_data(self, **kwargs):
        context = {}
        resultados = ResultadoBalance.objects.all()
        context["latest_results"] = resultados[:10]
        context["banks_count"] = Banco.objects.all().count()
        context["contracts_count"] = Contrato.objects.all().count()
        return context

class UploadContractsView(LoginRequiredMixin, FormView):
    form_class = UploadContractsForm  #qué formulario usar
    template_name = "irrbb_app/upload.html"
    success_url = reverse_lazy("dashboard")   #dónde ir después de procesar el formulario

    def form_valid(self, form):   #cuando el formulario es válido
        id_empleado = form.cleaned_data["id_empleado"]
        
        # Buscar el usuario por username
        try:
            uploaded_by = CustomUser.objects.get(id=id_empleado)
        except CustomUser.DoesNotExist:
            messages.error(self.request, f"❌ No existe un usuario con ID: {id_empleado}")
            return self.form_invalid(form)
        
        # Obtener el banco del usuario
        banco = uploaded_by.bank_name
        if not banco:
            messages.error(self.request, "❌ El usuario no tiene un banco asociado")
            return self.form_invalid(form)

        try:
            es_valido, errores = import_excel.validate_contracts_excel(form.cleaned_data["excel_file"])
            
            if not es_valido:
                messages.error(self.request, "⚠️ ERRORES EN EL EXCEL - Importación cancelada:")
                for e in errores:
                    messages.error(self.request, e)
                return self.form_invalid(form)
            
            count = import_excel.load_contracts_from_excel(form.cleaned_data["excel_file"], banco)
            messages.success(self.request, f" Importados {count} contratos correctamente")
        except Exception as e:
            messages.error(self.request, f" Error: {str(e)}")
            return self.form_invalid(form)

        contract_pricing.run_balance_pricing(banco, uploaded_by=uploaded_by)
        return redirect("dashboard")


class ResultsHistoryView(LoginRequiredMixin, ListView):
    template_name = "irrbb_app/results.html"
    model = ResultadoBalance
    context_object_name = "resultados"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bancos = Banco.objects.all()
        context["banks"] = bancos
        return context

class DetailView(LoginRequiredMixin, TemplateView):
    template_name = "irrbb_app/detail.html"

    def _process_contracts(self, resultado, curve_df):
        activos = {}
        pasivos = {}
        activos_cashflows = {}
        pasivos_cashflows = {}

        valuation_date = date.today()
        contratos = resultado.banco.contratos.all()

        #Agrupar contratos por producto y tipo
        for contrato in contratos:
            cf = build_cashflows(contrato, curve_df, valuation_date)
            
            if contrato.activo_pasivo == "ACTIVO":
                self._act_dict(contrato.producto, contrato, cf, activos, activos_cashflows)
            else:
                self._act_dict(contrato.producto, contrato, cf, pasivos, pasivos_cashflows)
        
        #Calcular EVE y NII para cada producto
        self._calculate_eve_nii(activos, activos_cashflows, curve_df)
        self._calculate_eve_nii(pasivos, pasivos_cashflows, curve_df)
        
        return activos, pasivos 
    
    def _act_dict(self, producto, contrato, cf, dict_obj, dict_cf):
        if producto not in dict_obj:
            dict_obj[producto] = {"count": 0, "nominal": 0}
            dict_cf[producto] = []
        dict_obj[producto]["count"] += 1
        dict_obj[producto]["nominal"] += contrato.nominal
        if not cf.empty:
            dict_cf[producto].append(cf)

# Activos es del tipo: "Central bank" : {"count": X,
#                                        "nominal": Y, 
#                                        "eve": { "base": Z, 
#                                                 "parallel_up": W, ...
#                                                 }, 
#                                        "nii": {...} 
#                                        }

# ResultadoBalance.objects es del tipo: "eve_base": X,
#                                   "eve_parallel_up": Y,
#                                  ...
#                                  "nii_parallel_down": Z
#  
    def _calculate_eve_nii(self, productos_dict, cashflows_dict, curve_df):
        for producto in productos_dict:
            cf_grupo = pd.concat(cashflows_dict[producto], ignore_index=True)
            eve_res = calculate_eve(cf_grupo, curve_df)
            nii_res = calculate_nii(cf_grupo, curve_df)

            scenario = {}
            for key, val in eve_res.items():
                scenario[key] = val
            for key, val in nii_res.items():
                scenario[key] = val

            productos_dict[producto]["scenario"] = scenario

    def get(self, request, *args, **kwargs):
        if request.GET.get("download") == "excel":
            return self._download_excel(*args, **kwargs)
        return super().get(request, *args, **kwargs)
    
    def _download_excel(self, *args, **kwargs):
        try:
            resultado = ResultadoBalance.objects.get(pk=self.kwargs["pk"])
            curve_df = build_default_curve()
            activos, pasivos = self._process_contracts(resultado, curve_df)
            return export_excel(resultado.fecha_calculo.strftime("%Y-%m-%d"), activos, pasivos, resultado.banco.nombre)
        
        except ResultadoBalance.DoesNotExist:
            raise Http404("Resultado de balance no encontrado")
        
        except Exception as e:
            raise Exception("Error al generar Excel:" + str(e))

    def get_context_data(self, **kwargs):
        try:
            resultado = ResultadoBalance.objects.get(pk=self.kwargs["pk"])
            curve_df = build_default_curve()
            activos, pasivos = self._process_contracts(resultado, curve_df)
            
            return {
                "resultado": resultado,
                "activos": activos,
                "pasivos": pasivos
            }
        except ResultadoBalance.DoesNotExist:
            raise Http404("Resultado de balance no encontrado")


def start(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "irrbb_app/start.html")

def download_template(request):
    wb = Workbook()
    ws = wb.active

    headers = ["NumeroContrato", "Producto", "ActivoPasivo", "Nominal", "FechaInicio", "FechaVencimiento", "TipoInteres", "Amortizacion", "CuponSpread", "Curva", "Frecuencia"]
    example_row1 = ["C001", "Crédito Hipotecario", "ACTIVO", 1000000, "2023-01-01", "2033-01-01", "FIJO", "ALEMANA", 5.0, "BASE", 1]
    example_row2 = ["D001", "Depósito a Plazo", "PASIVO", 500000, "2023-06-01", "2024-06-01", "VARIABLE", "BULLET", 3.0, "BASE", 4]
    ws.append(headers)
    ws.append(example_row1)
    ws.append(example_row2)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=Contratos_Template.xlsx'
    wb.save(response)
    return response


home = DashboardView.as_view()
upload_contracts = UploadContractsView.as_view()
results_history = ResultsHistoryView.as_view()
