from django.http import HttpResponse, Http404
from openpyxl import Workbook
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, TemplateView

from users.models import CustomUser

from .forms import UploadContractsForm
from .models import Banco, Contrato, ResultadoBalance
from .services import contract_pricing, import_excel
from .services.contract_pricing import _process_contracts
from .services.curve import build_default_curve
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
    success_url = reverse_lazy("dashboard")   
    
    def form_valid(self, form):   #cuando el formulario es válido
        id_empleado = form.cleaned_data["id_empleado"]
        
        try:
            uploaded_by = CustomUser.objects.get(id=id_empleado)
        except CustomUser.DoesNotExist:
            messages.error(self.request, f"No existe un usuario con ID: {id_empleado}")
            return self.form_invalid(form)
        
        banco = uploaded_by.bank_name
        if not banco:
            messages.error(self.request, "El usuario no tiene un banco asociado")
            return self.form_invalid(form)

        try:
            es_valido, errores = import_excel.validate_contracts_excel(form.cleaned_data["excel_file"])
            
            if not es_valido:
                messages.error(self.request, "Hay errores en el excel - Importación cancelada:")
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

    def get_queryset(self):
        user_banco = self.request.user.bank_name
        if user_banco:
            return ResultadoBalance.objects.filter(banco=user_banco)
        return ResultadoBalance.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.bank_name:
            context["banks"] = [self.request.user.bank_name]
        else:
            context["banks"] = []
        return context

class DetailView(LoginRequiredMixin, TemplateView):
    template_name = "irrbb_app/detail.html"

    def get(self, request, *args, **kwargs):
        if request.GET.get("download") == "excel":
            return self._download_excel(*args, **kwargs)
        return super().get(request, *args, **kwargs)
    
    def _download_excel(self, *args, **kwargs):
        try:
            resultado = ResultadoBalance.objects.get(pk=self.kwargs["pk"])
            curve_df = build_default_curve()
            activos, pasivos = _process_contracts(resultado.banco, curve_df)
            return export_excel(resultado.fecha_calculo.strftime("%Y-%m-%d"), activos, pasivos, resultado.banco.nombre)
        
        except ResultadoBalance.DoesNotExist:
            raise Http404("Resultado de balance no encontrado")
        
        except Exception as e:
            raise Exception("Error al generar Excel:" + str(e))

    def get_context_data(self, **kwargs):
        try:
            resultado = ResultadoBalance.objects.get(pk=self.kwargs["pk"])
            curve_df = build_default_curve()
            activos, pasivos = _process_contracts(resultado.banco, curve_df)
            
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
