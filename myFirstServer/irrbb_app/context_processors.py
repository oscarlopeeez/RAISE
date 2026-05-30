from .models import ResultadoBalance

def irrbb_context(request):
    if not request.user.is_authenticated:
        return {}
    banco = getattr(request.user, 'bank_name', None)
    if not banco:
        return {'irrbb': {'banco': None}}
    latest = ResultadoBalance.objects.filter(banco=banco).order_by('-fecha_calculo').first()
    curve_source = None
    valuation_date = None
    status = 'sin cálculos'
    if latest:
        curve_source = (latest.metadata or {}).get('curve_source', {})
        valuation_date = latest.valuation_date or latest.fecha_calculo.date()
        if latest.approved_by:
            status = f'aprobado · #{latest.pk}'
        else:
            status = f'pendiente checker · #{latest.pk}'
    bank_logo = None
    try:
        if banco:
            from pathlib import Path
            from django.conf import settings
            static_dir = Path(settings.BASE_DIR) / 'static' / 'irrbb_app' / 'logos' / 'banks'
            p_png = static_dir / f'banco_{banco.pk}.png'
            p_jpg = static_dir / f'banco_{banco.pk}.jpg'
            if p_png.exists():
                bank_logo = f'irrbb_app/logos/banks/banco_{banco.pk}.png'
            elif p_jpg.exists():
                bank_logo = f'irrbb_app/logos/banks/banco_{banco.pk}.jpg'
            else:
                bank_logo = None
    except Exception:
        bank_logo = None
    return {'irrbb': {'banco': banco, 'valuation_date': valuation_date, 'curve_source': curve_source, 'status': status, 'latest_calc_id': latest.pk if latest else None, 'bank_logo': bank_logo}}