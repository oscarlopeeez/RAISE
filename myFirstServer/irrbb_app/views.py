from django .http import HttpResponse ,Http404 
from openpyxl import Workbook 
from django .contrib import messages 
from django .contrib .auth import logout 
from django .contrib .auth .decorators import login_required 
from django .contrib .auth .mixins import LoginRequiredMixin 
from django .shortcuts import redirect ,render 
from django .urls import reverse_lazy 
from django .views .generic import FormView ,ListView ,TemplateView 
from users .models import CustomUser 
from .forms import UploadContractsForm 
from .models import Banco ,Contrato ,ResultadoBalance ,MarketCurve 
from .services import contract_pricing ,import_excel 
from .services .contract_pricing import _process_contracts 
from .services .curve import build_curve_from_market 
from .services .ecb_curve import fetch_ecb_curve 
import json 
from .services .export_j03 import export_excel 
from .services .portfolio_stats import portfolio_stats 
from .services .gap_analysis import gap_analysis 
import logging 
EVE_SCENARIOS =[('Parallel up','eve_parallel_up'),('Parallel down','eve_parallel_down'),('Steepener','eve_steepener'),('Flattener','eve_flattener'),('Short up','eve_short_up'),('Short down','eve_short_down')]
NII_SCENARIOS =[('Parallel up','nii_parallel_up'),('Parallel down','nii_parallel_down')]
SOT_EVE_THRESHOLD =0.15 
SOT_NII_THRESHOLD =0.05 

def _scenario_rows (obj ,base_attr ,scenarios ):
    base =getattr (obj ,base_attr )
    rows =[]
    for label ,attr in scenarios :
        val =getattr (obj ,attr )
        delta =val -base 
        delta_pct =delta /base *100 if base else 0 
        rows .append ({'label':label ,'attr':attr ,'value':val ,'delta':delta ,'delta_pct':delta_pct ,'sign':'up'if delta >0 else 'down'if delta <0 else ''})
    return rows 
def _worst (rows ):
    if not rows :
        return None 
    return min (rows ,key =lambda r :r ['delta'])

def _build_trend (rows ,w =600 ,h =120 ,pad =20 ):
    if not rows :
        return None 
    values_per_series ={'eve_base':[r ['eve_base']for r in rows ],'eve_up':[r ['eve_parallel_up']for r in rows ],'eve_down':[r ['eve_parallel_down']for r in rows ],'nii_base':[r ['nii_base']for r in rows ]}
    all_eve =values_per_series ['eve_base']+values_per_series ['eve_up']+values_per_series ['eve_down']
    eve_min ,eve_max =(min (all_eve ),max (all_eve ))
    nii_min ,nii_max =(min (values_per_series ['nii_base']),max (values_per_series ['nii_base']))
    n =len (rows )

    def line (values ,vmin ,vmax ):
        if vmax ==vmin or n <2 :
            mid =h /2 
            return ' '.join ((f'{pad +i *(w -2 *pad )/max (n -1 ,1 ):.1f},{mid :.1f}'for i in range (n )))
        coords =[]
        for i ,v in enumerate (values ):
            x =pad +i *(w -2 *pad )/(n -1 )
            y =h -pad -(v -vmin )/(vmax -vmin )*(h -2 *pad )
            coords .append (f'{x :.1f},{y :.1f}')
        return ' '.join (coords )
    return {'n':n ,'w':w ,'h':h ,'eve_base':line (values_per_series ['eve_base'],eve_min ,eve_max ),'eve_up':line (values_per_series ['eve_up'],eve_min ,eve_max ),'eve_down':line (values_per_series ['eve_down'],eve_min ,eve_max ),'nii_base':line (values_per_series ['nii_base'],nii_min ,nii_max ),'eve_min':eve_min ,'eve_max':eve_max ,'nii_min':nii_min ,'nii_max':nii_max ,'dates':[r ['fecha_calculo']for r in rows ],'latest_eve':values_per_series ['eve_base'][-1 ]if values_per_series ['eve_base']else 0 ,'latest_nii':values_per_series ['nii_base'][-1 ]if values_per_series ['nii_base']else 0 }

def _sensitivity_metrics (r ):
    shock_bp =(r .metadata or {}).get ('shocks_bp',{}).get ('parallel',225 )or 225 
    delta_up =r .eve_parallel_up -r .eve_base 
    delta_down =r .eve_parallel_down -r .eve_base 
    dv01 =(abs (delta_up )+abs (delta_down ))/2 /shock_bp 
    dv01_signed =delta_up /shock_bp 
    mod_dur =-dv01_signed *10000 /r .eve_base if r .eve_base else 0 
    return {'dv01':dv01 ,'dv01_signed':dv01_signed ,'mod_duration':mod_dur ,'shock_bp':shock_bp }

def _summary_for_result (r ):
    eve_rows =_scenario_rows (r ,'eve_base',EVE_SCENARIOS )
    nii_rows =_scenario_rows (r ,'nii_base',NII_SCENARIOS )
    curve_source =(r .metadata or {}).get ('curve_source',{})

    try :
        fecha_calculo_str =r .fecha_calculo .strftime ('%Y-%m-%d %H:%M')if r .fecha_calculo else '-'
    except Exception :
        fecha_calculo_str =str (r .fecha_calculo )if getattr (r ,'fecha_calculo',None )else '-'
    try :
        if getattr (r ,'valuation_date',None ):
            valuation_str =r .valuation_date .isoformat ()
        else :
            valuation_str =(r .metadata or {}).get ('valuation_date')or '-'
    except Exception :
        valuation_str ='-'
    curve_ref =curve_source .get ('reference_date')if curve_source else None 
    return {'obj':r ,'eve_worst':_worst (eve_rows ),'nii_worst':_worst (nii_rows ),'sot':_sot_compliance (r ,eve_rows ,nii_rows ),'sens':_sensitivity_metrics (r ),'curve_source':curve_source ,'fecha_calculo_str':fecha_calculo_str ,'valuation_date_str':valuation_str ,'curve_ref':curve_ref }

def _sot_compliance (resultado ,eve_rows ,nii_rows ):
    tier1 =resultado .tier1_capital or (resultado .banco .tier1_capital if resultado .banco else 0 )
    if not tier1 :
        return {'tier1':0 ,'ok':False ,'missing_tier1':True }
    worst_eve =_worst (eve_rows )
    worst_nii =_worst (nii_rows )
    eve_loss =abs (min (0 ,worst_eve ['delta']))if worst_eve else 0 
    nii_loss =abs (min (0 ,worst_nii ['delta']))if worst_nii else 0 
    eve_pct =eve_loss /tier1 *100 
    nii_pct =nii_loss /tier1 *100 
    eve_pass =eve_pct <=SOT_EVE_THRESHOLD *100 
    nii_pass =nii_pct <=SOT_NII_THRESHOLD *100 
    return {'tier1':tier1 ,'eve_loss':eve_loss ,'nii_loss':nii_loss ,'eve_pct':eve_pct ,'nii_pct':nii_pct ,'eve_threshold_pct':SOT_EVE_THRESHOLD *100 ,'nii_threshold_pct':SOT_NII_THRESHOLD *100 ,'eve_pass':eve_pass ,'nii_pass':nii_pass ,'eve_worst_label':worst_eve ['label']if worst_eve else None ,'nii_worst_label':worst_nii ['label']if worst_nii else None ,'ok':eve_pass and nii_pass ,'missing_tier1':False }

def _build_alerts (user ,banco ,resultados ,latest_calc ):
    from datetime import date ,timedelta 
    alerts =[]
    pending_to_approve =resultados .filter (approved_by__isnull =True ).exclude (uploaded_by =user )
    n_to_approve =pending_to_approve .count ()
    if n_to_approve >0 :
        alerts .append ({'level':'warn','label':'PARA APROBAR','text':f"{n_to_approve } cálculo{('s'if n_to_approve >1 else '')} esperan tu revisión como checker.",'url':'/calculos/pendientes/','url_text':'Ir a bandeja →'})
    pending_own =resultados .filter (approved_by__isnull =True ,uploaded_by =user ).count ()
    if pending_own >0 :
        alerts .append ({'level':'neutral','label':'TUS PENDIENTES','text':f"Tienes {pending_own } cálculo{('s'if pending_own >1 else '')} sin aprobar. Otro usuario debe revisarlos.",'url':'/calculos/','url_text':'Ver cálculos →'})
    last_market =MarketCurve .objects .first ()
    if last_market is None :
        alerts .append ({'level':'warn','label':'CURVA','text':'Nunca has descargado la curva BCE. Descarga la curva BCE para usar datos de mercado.','url':'/curva/','url_text':'Ver curva →'})
    else :
        days_old =(date .today ()-last_market .reference_date ).days 
        if days_old >7 :
            alerts .append ({'level':'warn','label':'CURVA','text':f'La curva BCE es de hace {days_old } días ({last_market .reference_date }). Considera refrescarla.','url':'/curva/','url_text':'Ver curva →'})
    if latest_calc and last_market :
        curve_source =(latest_calc .metadata or {}).get ('curve_source',{})
        if curve_source .get ('type')!='market':
            alerts .append ({'level':'neutral','label':'CURVA','text':'Tu último cálculo no usó la curva de mercado. Recalcula con la curva BCE para reflejar mercado actual.','url':'/recalculate/market/','url_text':'Recalcular con BCE →'})
    if banco :
        today =date .today ()
        vencidos =banco .contratos .filter (fecha_vencimiento__lt =today ).count ()
        if vencidos >0 :
            alerts .append ({'level':'neutral','label':'DATOS','text':f"{vencidos } contrato{('s'if vencidos >1 else '')} ya pasaron su fecha de vencimiento. Considera depurarlos.",'url':'/cartera/contratos/?solo_vencidos=1','url_text':'Filtrar vencidos →'})
    return alerts 

class TodayView (LoginRequiredMixin ,TemplateView ):
    template_name ='irrbb_app/today.html'

    def get_context_data (self ,**kwargs ):
        user =self .request .user 
        banco =user .bank_name 
        resultados =ResultadoBalance .objects .filter (banco =banco )if banco else ResultadoBalance .objects .none ()
        latest =resultados .order_by ('-fecha_calculo').first ()
        trend =None 
        alerts =_build_alerts (user ,banco ,resultados ,latest )
        latest_summary =_summary_for_result (latest )if latest else None 
        portfolio =portfolio_stats (banco )if banco else None 
        main_risk_driver =None 
        try :
            if latest_summary :
                sot =latest_summary .get ('sot',{})
                eve_w =latest_summary .get ('eve_worst')
                nii_w =latest_summary .get ('nii_worst')
                if not sot .get ('eve_pass'):
                    if eve_w :
                        main_risk_driver =f"Peor escenario EVE: {eve_w ['label']}."
                if not main_risk_driver and portfolio :
                    bullet_pct =0 
                    for a in portfolio .get ('amortizacion',[]):
                        if str (a ['tipo']).lower ().startswith ('bullet'):
                            bullet_pct =a .get ('pct',0 )
                    if portfolio .get ('pct_fijo',0 )>=60 :
                        main_risk_driver ='Alta exposición a tipo fijo.'
                    elif bullet_pct >=40 :
                        main_risk_driver ='Alta exposición bullet a tipo fijo.'
                    elif portfolio .get ('pct_variable',0 )>=60 :
                        main_risk_driver ='La exposición a tipo variable puede aumentar la sensibilidad del NII.'
                if not main_risk_driver :
                    if eve_w :
                        main_risk_driver =f"{eve_w ['label']} impulsa la sensibilidad del EVE."
                    else :
                        main_risk_driver ='No se detecta un factor de riesgo dominante.'
        except Exception :
            main_risk_driver ='No se detecta un factor de riesgo dominante.'
        pending_to_approve =resultados .filter (approved_by__isnull =True ).exclude (uploaded_by =user ).count ()if banco else 0 
        pending_own =resultados .filter (approved_by__isnull =True ,uploaded_by =user ).count ()if banco else 0 
        return {'banco':banco ,'latest':latest_summary ,'trend':trend ,'alerts':alerts ,'n_calcs':resultados .count (),'portfolio':portfolio ,'main_risk_driver':main_risk_driver ,'pending_to_approve':pending_to_approve ,'pending_own':pending_own }

class ContratosListView (LoginRequiredMixin ,ListView ):
    template_name ='irrbb_app/contratos.html'
    context_object_name ='contratos'
    paginate_by =50 

    def get_queryset (self ):
        banco =self .request .user .bank_name 
        if not banco :
            return Contrato .objects .none ()
        qs =banco .contratos .all ().order_by ('numero_contrato')
        q =self .request .GET .get ('q','').strip ()
        if q :
            qs =qs .filter (numero_contrato__icontains =q )
        producto =self .request .GET .get ('producto','').strip ()
        if producto :
            qs =qs .filter (producto =producto )
        activo_pasivo =self .request .GET .get ('activo_pasivo','').strip ()
        if activo_pasivo :
            qs =qs .filter (activo_pasivo =activo_pasivo )
        tipo_interes =self .request .GET .get ('tipo_interes','').strip ()
        if tipo_interes :
            qs =qs .filter (tipo_interes =tipo_interes )
        if self .request .GET .get ('solo_vencidos')=='1':
            from datetime import date 
            qs =qs .filter (fecha_vencimiento__lt =date .today ())
        return qs 

    def get_context_data (self ,**kwargs ):
        context =super ().get_context_data (**kwargs )
        banco =self .request .user .bank_name 
        if banco :
            all_qs =banco .contratos .all ()
            context ['productos']=sorted (set (all_qs .values_list ('producto',flat =True )))
        else :
            context ['productos']=[]
        context ['filters']={'q':self .request .GET .get ('q',''),'producto':self .request .GET .get ('producto',''),'activo_pasivo':self .request .GET .get ('activo_pasivo',''),'tipo_interes':self .request .GET .get ('tipo_interes',''),'solo_vencidos':self .request .GET .get ('solo_vencidos')=='1'}
        context ['banco']=banco 
        return context 

class AprobacionesView (LoginRequiredMixin ,TemplateView ):
    template_name ='irrbb_app/aprobaciones.html'

    def get_context_data (self ,**kwargs ):
        user =self .request .user 
        banco =user .bank_name 
        pendientes =(ResultadoBalance .objects .filter (banco =banco ,approved_by__isnull =True )if banco else ResultadoBalance .objects .none ()).order_by ('-fecha_calculo')
        para_aprobar =[_summary_for_result (r )for r in pendientes .exclude (uploaded_by =user )]
        propios =[_summary_for_result (r )for r in pendientes .filter (uploaded_by =user )]
        return {'banco':banco ,'para_aprobar':para_aprobar ,'propios':propios }

class UploadContractsView (LoginRequiredMixin ,FormView ):
    form_class =UploadContractsForm 
    template_name ='irrbb_app/upload.html'
    success_url =reverse_lazy ('dashboard')

    def form_valid (self ,form ):
        uploaded_by =self .request .user 
        banco =uploaded_by .bank_name 
        if not banco :
            messages .error (self .request ,'El usuario no tiene un banco asociado')
            return self .form_invalid (form )
        try :
            es_valido ,errores =import_excel .validate_contracts_excel (form .cleaned_data ['excel_file'])
            if not es_valido :
                messages .error (self .request ,'Hay errores en el excel - Importación cancelada:')
                for e in errores :
                    messages .error (self .request ,e )
                return self .form_invalid (form )
            result =import_excel .load_contracts_from_excel (form .cleaned_data ['excel_file'],banco )
            messages .success (self .request ,f"Import OK: {result ['inserted']} nuevos, {result ['updated']} actualizados ({result ['total']} total)")
        except Exception as e :
            messages .error (self .request ,f'Error de importación: {str (e )}')
            return self .form_invalid (form )

        market_curve =MarketCurve .objects .first ()
        if not market_curve :
            messages .error (self .request ,'No hay curva de mercado descargada. Ejecuta el comando fetch_ecb_curve antes de importar.')
            return self .form_invalid (form )
        contract_pricing .run_balance_pricing (banco ,uploaded_by =uploaded_by ,market_curve =market_curve, contract_ids=result.get('contract_ids'))
        return redirect ('dashboard')

class ResultsHistoryView (LoginRequiredMixin ,ListView ):
    template_name ='irrbb_app/results.html'
    model =ResultadoBalance 
    context_object_name ='resultados'
    paginate_by =20 

    def get_queryset (self ):
        user_banco =self .request .user .bank_name 
        if user_banco :
            return ResultadoBalance .objects .filter (banco =user_banco ).order_by ('-fecha_calculo')
        return ResultadoBalance .objects .none ()

    def get_context_data (self ,**kwargs ):
        context =super ().get_context_data (**kwargs )
        context ['summaries']=[_summary_for_result (r )for r in context ['resultados']]
        context ['banco']=self .request .user .bank_name 
        return context 

def _producto_rows (activos ,pasivos ):
    rows =[]
    for tipo ,group in (('ACTIVO',activos ),('PASIVO',pasivos )):
        for producto ,datos in group .items ():
            sc =datos .get ('scenario',{})
            base =sc .get ('eve_base',0 )
            up =sc .get ('eve_parallel_up',0 )
            down =sc .get ('eve_parallel_down',0 )
            rows .append ({'tipo':tipo ,'producto':producto ,'count':datos .get ('count',0 ),'nominal':datos .get ('nominal',0 ),'eve_base':base ,'eve_up':up ,'eve_down':down ,'delta_up':up -base ,'delta_down':down -base ,'nii_base':sc .get ('nii_base',0 ),'nii_up':sc .get ('nii_parallel_up',0 ),'nii_down':sc .get ('nii_parallel_down',0 )})
    rows .sort (key =lambda r :-abs (r ['eve_base']))
    return rows 

def _top_contributors (contributions ,scenario_key ,n =10 ):
    if not contributions :
        return []
    rows =[]
    for c in contributions :
        scenario_val =c .get (scenario_key ,0 )
        delta =scenario_val -c .get ('eve_base',0 )
        rows .append ({**c ,'eve_worst_value':scenario_val ,'delta':delta })
    rows .sort (key =lambda r :r ['delta'])
    return rows [:n ]

class DetailView (LoginRequiredMixin ,TemplateView ):
    template_name ='irrbb_app/detail.html'

    def get (self ,request ,*args ,**kwargs ):
        if request .GET .get ('download')=='excel':
            return self ._download_excel (request ,*args ,**kwargs )
        if request .GET .get ('approve')=='1':
            return self ._approve (request ,*args ,**kwargs )
        return super ().get (request ,*args ,**kwargs )

    def _approve (self ,request ,*args ,**kwargs ):
        try :
            resultado =ResultadoBalance .objects .get (pk =self .kwargs ['pk'])
        except ResultadoBalance .DoesNotExist :
            raise Http404 ('Resultado no encontrado')
        if resultado .uploaded_by_id ==request .user .id :
            messages .error (request ,'No puedes aprobar tu propio cálculo (segregación de funciones).')
            return redirect ('detail',pk =resultado .pk )
        from django .utils import timezone 
        resultado .approved_by =request .user 
        resultado .approved_at =timezone .now ()
        resultado .save (update_fields =['approved_by','approved_at'])
        messages .success (request ,f'Cálculo #{resultado .pk } aprobado.')
        return redirect ('detail',pk =resultado .pk )

    def _download_excel (self ,request ,*args ,**kwargs ):
        try :
            resultado =ResultadoBalance .objects .get (pk =self .kwargs ['pk'])
        except ResultadoBalance .DoesNotExist :
            raise Http404 ('Resultado de balance no encontrado')
        if not resultado .approved_by :
            messages .error (request ,'El cálculo debe estar aprobado antes de descargar el J03.')
            return redirect ('detail',pk =resultado .pk )
        try :
            contributions =(resultado .metadata or {}).get ('contributions')
            if contributions :
                logging .getLogger (__name__ ).info ('J03 generated from calculation snapshot, not live contracts.')
                try :
                    messages .info (request ,'J03 generated from calculation snapshot, not live contracts.')
                except Exception :
                    pass 
                activos ={}
                pasivos ={}
                scenario_keys =['eve_base','eve_parallel_up','eve_parallel_down','eve_steepener','eve_flattener','eve_short_up','eve_short_down','nii_base','nii_parallel_up','nii_parallel_down']
                for c in contributions :
                    producto =c .get ('producto')
                    tipo =c .get ('activo_pasivo')
                    target =activos if tipo =='ACTIVO'else pasivos 
                    if producto not in target :
                        target [producto ]={'count':0 ,'nominal':0.0 ,'scenario':{},'contracts':[]}
                    target [producto ]['count']+=1 
                    target [producto ]['nominal']+=float (c .get ('nominal',0.0 )or 0.0 )
                    sc =target [producto ].setdefault ('scenario',{})
                    for k in scenario_keys :
                        sc [k ]=sc .get (k ,0.0 )+float (c .get (k ,0.0 )or 0.0 )

                    try :
                        target [producto ]['contracts'].append ({'nominal':float (c .get ('nominal',0.0 )or 0.0 ),'fecha_vencimiento':c .get ('fecha_vencimiento')})
                    except Exception :
                        pass 

                from datetime import date 
                try :
                    val_date =resultado .valuation_date if hasattr (resultado ,'valuation_date')and resultado .valuation_date else None 
                except Exception :
                    val_date =None 
                if val_date is None :
                    try :
                        val_date =resultado .fecha_calculo .date ()
                    except Exception :
                        val_date =None 
                for d in (activos ,pasivos ):
                    for prod ,info in d .items ():
                        contracts =info .get ('contracts',[])or []
                        total =0.0 
                        weighted_years =0.0 
                        for cm in contracts :
                            nom =cm .get ('nominal',0.0 )or 0.0 
                            total +=nom 
                            fv =cm .get ('fecha_vencimiento')
                            yrs =0.0 
                            if fv and val_date :
                                try :
                                    from datetime import datetime as _dt 
                                    fv_date =_dt .fromisoformat (fv ).date ()
                                    yrs =(fv_date -val_date ).days /365.25 
                                    if yrs <0 :
                                        yrs =0.0 
                                except Exception :
                                    yrs =0.0 
                            weighted_years +=yrs *nom 
                        info ['carrying_amount']=total 
                        info ['duration']=(weighted_years /total )if total else 0.0 
                return export_excel (resultado .fecha_calculo .strftime ('%Y-%m-%d'),activos ,pasivos ,resultado .banco .nombre )
            logging .getLogger (__name__ ).warning ('J03 exported from live contracts fallback (no snapshot present).')
            try :
                messages .warning (request ,'Fallback only for legacy results without snapshot.')
            except Exception :
                pass 

            market_curve =MarketCurve .objects .first ()
            if not market_curve :
                messages .error (request ,'No hay curva de mercado disponible. Ejecuta el comando fetch_ecb_curve.')
                return redirect ('dashboard')
            curve_df =build_curve_from_market (market_curve )
            activos ,pasivos =_process_contracts (resultado .banco ,curve_df ,resultado .valuation_date )
            return export_excel (resultado .fecha_calculo .strftime ('%Y-%m-%d'),activos ,pasivos ,resultado .banco .nombre )
        except Exception as e :
            raise Exception ('Error al generar Excel:'+str (e ))

    def get_context_data (self ,**kwargs ):
        try :
            resultado =ResultadoBalance .objects .get (pk =self .kwargs ['pk'])
        except ResultadoBalance .DoesNotExist :
            raise Http404 ('Resultado de balance no encontrado')

        market =MarketCurve .objects .first ()
        if not market :
            raise Http404 ('No hay curva de mercado disponible. Ejecuta el comando fetch_ecb_curve.')
        curve_df =build_curve_from_market (market )
        activos ,pasivos =_process_contracts (resultado .banco ,curve_df ,resultado .valuation_date )
        eve_rows =_scenario_rows (resultado ,'eve_base',EVE_SCENARIOS )
        nii_rows =_scenario_rows (resultado ,'nii_base',NII_SCENARIOS )
        sot =_sot_compliance (resultado ,eve_rows ,nii_rows )
        contributions =(resultado .metadata or {}).get ('contributions',[])
        curve_source =(resultado .metadata or {}).get ('curve_source',{})
        worst_eve =_worst (eve_rows )
        worst_scenario_key =worst_eve ['attr']if worst_eve else 'eve_parallel_up'
        top_losers =_top_contributors (contributions ,worst_scenario_key ,n =10 )
        gap =gap_analysis (resultado .banco ,resultado .valuation_date )

        bank_logo =None 
        try :
            if resultado .banco :
                bank_logo =f'irrbb_app/logos/banks/banco_{resultado .banco .pk }.png'
        except Exception :
            bank_logo =None 
        return {'resultado':resultado ,'eve_rows':eve_rows ,'nii_rows':nii_rows ,'eve_worst':worst_eve ,'nii_worst':_worst (nii_rows ),'sot':sot ,'sens':_sensitivity_metrics (resultado ),'top_losers':top_losers ,'top_losers_scenario':worst_eve ['label']if worst_eve else '','gap':gap ,'producto_rows':_producto_rows (activos ,pasivos ),'portfolio':portfolio_stats (resultado .banco ),'has_snapshot':bool (contributions ),'curve_source':curve_source ,'bank_logo':bank_logo }

def _curve_implied_forwards (curve_snapshot ):
    forwards =[]
    sorted_pts =sorted (curve_snapshot ,key =lambda x :x ['maturity_years'])
    for i in range (len (sorted_pts )-1 ):
        t1 =sorted_pts [i ]['maturity_years']
        t2 =sorted_pts [i +1 ]['maturity_years']
        r1 =sorted_pts [i ]['rate_flat_curve']
        r2 =sorted_pts [i +1 ]['rate_flat_curve']
        if t2 -t1 <=0 :
            continue 
        try :
            fwd =((1 +r2 )**t2 /(1 +r1 )**t1 )**(1 /(t2 -t1 ))-1 
        except Exception :
            fwd =0 
        forwards .append ({'from':t1 ,'to':t2 ,'r1':r1 ,'r2':r2 ,'rate':fwd })
    return forwards 

@login_required 
def recalculate_market (request ):
    banco =request .user .bank_name 
    if not banco :
        messages .error (request ,'Tu usuario no tiene banco asociado.')
        return redirect ('dashboard')
    market_curve =MarketCurve .objects .first ()
    if not market_curve :
        messages .error (request ,"No hay curva de mercado. Ejecuta primero el comando 'fetch_ecb_curve'.")
        return redirect ('dashboard')
    res =contract_pricing .run_balance_pricing (banco ,uploaded_by =request .user ,market_curve =market_curve )
    if res is None :
        messages .error (request ,'El banco no tiene contratos.')
        return redirect ('dashboard')
    r =res ['resultado']
    messages .success (request ,f'Cálculo #{r .pk } generado con curva BCE de {market_curve .reference_date }.')
    return redirect ('detail',pk =r .pk )

class CurveView (LoginRequiredMixin ,TemplateView ):
    template_name ='irrbb_app/curve.html'

    def post (self ,request ,*args ,**kwargs ):
        try :
            ref_date ,points ,errors =fetch_ecb_curve ()
        except RuntimeError as e :
            messages .error (request ,f'Error fetching ECB curve: {e }')
            return redirect ('curve')
        try :
            mc =MarketCurve .objects .create (source =MarketCurve .SOURCE_ECB ,reference_date =ref_date ,currency ='EUR',tenors =points )
            messages .success (request ,f'Curva BCE actualizada: referencia {ref_date } ({len (points )} tenores)')
        except Exception as e :
            messages .error (request ,f'No se pudo guardar la curva en la base de datos: {e }')
        return redirect ('curve')

    def get_context_data (self ,**kwargs ):

        market =MarketCurve .objects .first ()
        points =[]
        if market :
            curve_df =build_curve_from_market (market )
            for _ ,row in curve_df .iterrows ():
                points .append ({'maturity_years':float (row ['maturity_years']),'rate_flat_curve':float (row ['rate_flat_curve']),'rate_base_curve':float (row ['rate_base_curve'])/10000 ,'rate_parallel_up':float (row ['rate_parallel_up_curve'])/10000 ,'rate_parallel_down':float (row ['rate_parallel_down_curve'])/10000 ,'rate_short_up':float (row ['rate_short_up_curve'])/10000 ,'rate_short_down':float (row ['rate_short_down_curve'])/10000 ,'rate_steepener':float (row ['rate_steepener_curve'])/10000 ,'rate_flattener':float (row ['rate_flattener_curve'])/10000 })
        else :

            points =[]
        points .sort (key =lambda p :p ['maturity_years'])
        forwards =_curve_implied_forwards (points )
        if points :
            min_y =min ((p ['rate_parallel_down']for p in points ))
            max_y =max ((p ['rate_parallel_up']for p in points ))
            max_x =max ((p ['maturity_years']for p in points ))
        else :
            min_y ,max_y ,max_x =(0 ,0.05 ,10 )

        def to_svg (series_key ,w =800 ,h =300 ,pad =40 ):
            if not points or max_y ==min_y :
                return ''
            range_y =max_y -min_y or 1 
            range_x =max_x or 1 
            coords =[]
            for p in points :
                x =pad +p ['maturity_years']/range_x *(w -2 *pad )
                y =h -pad -(p [series_key ]-min_y )/range_y *(h -2 *pad )
                coords .append (f'{x :.1f},{y :.1f}')
            return ' '.join (coords )
        svg ={'width':800 ,'height':300 ,'pad':40 ,'base':to_svg ('rate_base_curve'),'up':to_svg ('rate_parallel_up'),'down':to_svg ('rate_parallel_down'),'min_y':min_y ,'max_y':max_y ,'max_x':max_x }
        market =MarketCurve .objects .first ()
        market_points =[]
        market_diff =[]
        if market :
            market_points =sorted (market .tenors ,key =lambda x :x ['maturity_years'])



            market_diff =[]
        svg_points =[]
        market_svg_points =[]
        w ,h ,pad =(svg ['width'],svg ['height'],svg ['pad'])
        range_y =svg ['max_y']-svg ['min_y']or 1 
        range_x =svg ['max_x']or 1 
        for p in points :
            x =pad +p ['maturity_years']/range_x *(w -2 *pad )
            y =h -pad -(p ['rate_base_curve']-svg ['min_y'])/range_y *(h -2 *pad )
            svg_points .append ({'x':round (x ,1 ),'y':round (y ,1 ),'maturity':p ['maturity_years'],'rate':p ['rate_base_curve']})
        if market_points :
            for mp in market_points :
                mx =pad +mp ['maturity_years']/range_x *(w -2 *pad )
                my =h -pad -(mp ['rate']-svg ['min_y'])/range_y *(h -2 *pad )
                market_svg_points .append ({'x':round (mx ,1 ),'y':round (my ,1 ),'maturity':mp ['maturity_years'],'rate':mp ['rate'],'label':mp .get ('label')})

        observations =[]


        if market and (__import__ ('datetime').date .today ()-market .reference_date ).days >30 :
            observations .append ('Consider refresh curve if data is older than 30 days.')
        if not observations :
            observations =['-']

        return {'points':points ,'forwards':forwards ,'svg':svg ,'shocks':{'parallel':225 ,'short':350 ,'long':200 },'market':market ,'market_points':market_points ,'market_diff':[],'svg_points':svg_points ,'market_svg_points':market_svg_points ,'chart_json':json .dumps ({'datasets':[{'label':'Curva base','data':[{'x':p ['maturity_years'],'y':p ['rate_base_curve']}for p in points ],'borderColor':'#58a6ff','backgroundColor':'#58a6ff','tension':0.2 ,'pointRadius':2 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Parallel up (+225bp)','data':[{'x':p ['maturity_years'],'y':p ['rate_parallel_up']}for p in points ],'borderColor':'#f85149','backgroundColor':'#f85149','borderDash':[6 ,4 ],'tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Parallel down (-225bp)','data':[{'x':p ['maturity_years'],'y':p ['rate_parallel_down']}for p in points ],'borderColor':'#3fb950','backgroundColor':'#3fb950','borderDash':[6 ,4 ],'tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Short up','data':[{'x':p ['maturity_years'],'y':p ['rate_short_up']}for p in points ],'borderColor':'#9bdbff','backgroundColor':'#9bdbff','tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Short down','data':[{'x':p ['maturity_years'],'y':p ['rate_short_down']}for p in points ],'borderColor':'#5ee3a1','backgroundColor':'#5ee3a1','tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Steepener','data':[{'x':p ['maturity_years'],'y':p ['rate_steepener']}for p in points ],'borderColor':'#c084fc','backgroundColor':'#c084fc','tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Flattener','data':[{'x':p ['maturity_years'],'y':p ['rate_flattener']}for p in points ],'borderColor':'#f5b3ff','backgroundColor':'#f5b3ff','tension':0.2 ,'pointRadius':0 ,'borderWidth':1 ,'yAxisID':'y','type':'line'},{'label':'Mercado (BCE)','data':[{'x':mp ['maturity_years'],'y':mp ['rate']}for mp in market_points ],'type':'scatter','backgroundColor':'#ffd33d','pointRadius':6 ,'yAxisID':'y'}],'xMin':min ((p ['maturity_years']for p in points ))if points else 0 ,'xMax':max ((p ['maturity_years']for p in points ))if points else 10 }),'kpis':{'max_diff_bp':0 },'selected_scenario':(self .request .GET .get ('scenario')if hasattr (self ,'request')and getattr (self .request ,'GET',None )else None )or 'rate_parallel_up','compact_market_summary':{'max_diff_bp':0 ,'tenor_max_diff':None ,'reference_date':market .reference_date if market else None ,'recommendation':'NO_DATA'if not market else 'OUTDATED'if (__import__ ('datetime').date .today ()-market .reference_date ).days >30 else 'OK'},'compact_table':[{'maturity_years':p ['maturity_years'],'base':p ['rate_base_curve'],'scenario_rate':p .get ((self .request .GET .get ('scenario')if hasattr (self ,'request')and getattr (self .request ,'GET',None )else None )or 'rate_parallel_up'),'diff_bp':(p .get ((self .request .GET .get ('scenario')if hasattr (self ,'request')and getattr (self .request ,'GET',None )else None )or 'rate_parallel_up')-p ['rate_base_curve'])*10000 }for p in points ],'observations':observations }

def start (request ):
    if request .user .is_authenticated :
        return redirect ('dashboard')
    # Mostrar contadores públicos en la página de inicio para dar sensación de adopción
    n_bancos = Banco.objects.count()
    n_contratos = Contrato.objects.count()
    n_calculos = ResultadoBalance.objects.count()
    return render(request, 'irrbb_app/start.html', {'n_bancos': n_bancos, 'n_contratos': n_contratos, 'n_calculos': n_calculos})

def LogOutView (request ):
    logout (request )
    messages .success (request ,'Has salido correctamente.')
    return redirect ('start')

def download_template (request ):
    wb =Workbook ()
    ws =wb .active 
    headers =['NumeroContrato','Producto','ActivoPasivo','Nominal','FechaInicio','FechaVencimiento','TipoInteres','Amortizacion','CuponSpread','Curva','Frecuencia']
    example_row1 =['C001','Crédito Hipotecario','ACTIVO',1000000 ,'2023-01-01','2033-01-01','FIJO','ALEMANA',5.0 ,'BASE',1 ]
    example_row2 =['D001','Depósito a Plazo','PASIVO',500000 ,'2023-06-01','2024-06-01','VARIABLE','BULLET',3.0 ,'BASE',4 ]
    ws .append (headers )
    ws .append (example_row1 )
    ws .append (example_row2 )
    response =HttpResponse (content_type ='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response ['Content-Disposition']='attachment; filename=Contratos_Template.xlsx'
    wb .save (response )
    return response 
home =TodayView .as_view ()
today_view =TodayView .as_view ()
upload_contracts =UploadContractsView .as_view ()
results_history =ResultsHistoryView .as_view ()
curve_view =CurveView .as_view ()

class CarteraView (LoginRequiredMixin ,TemplateView ):
    template_name ='irrbb_app/cartera.html'

    def get_context_data (self ,**kwargs ):
        banco =self .request .user .bank_name 
        portfolio =portfolio_stats (banco )if banco else None 
        ctx ={'banco':banco ,'portfolio':portfolio ,'n_contratos':banco .contratos .count ()if banco else 0 }
        if not portfolio :
            return ctx 
        kpis ={'total_contracts':portfolio ['n_contratos'],'assets_nominal':portfolio ['nominal_activos'],'liabilities_nominal':portfolio ['nominal_pasivos'],'net_gap':portfolio ['gap'],'pct_fixed':portfolio ['pct_fijo'],'pct_variable':portfolio ['pct_variable'],'avg_asset_maturity':portfolio ['plazo_medio_activos'],'avg_liability_maturity':portfolio ['plazo_medio_pasivos'],'duration_mismatch':portfolio ['plazo_medio_activos']-portfolio ['plazo_medio_pasivos']}
        reg_capital =getattr (banco ,'tier1_capital',None )
        sot_info ={'regulatory_capital_base':reg_capital ,'sot_threshold':SOT_EVE_THRESHOLD *100 }
        badges =[]
        if kpis ['net_gap']<0 :
            badges .append ('GAP NEGATIVO')
        else :
            badges .append ('GAP POSITIVO')
        if abs (kpis ['duration_mismatch'])>2.0 :
            badges .append ('DESAJUSTE DE DURACIÓN')
        if kpis ['pct_fixed']>=70 :
            badges .append ('ALTA EXPOSICIÓN A TIPO FIJO')
        kris =[]
        if kpis ['assets_nominal']>kpis ['liabilities_nominal']and kpis ['avg_asset_maturity']>kpis ['avg_liability_maturity']:
            kris .append ('Activos superan a pasivos en tramos de largo plazo.')
        if kpis ['avg_liability_maturity']<kpis ['avg_asset_maturity']-1.0 :
            kris .append ('El plazo de los pasivos es más corto que el de los activos.')
        buckets =[(0 ,1 ),(1 ,3 ),(3 ,5 ),(5 ,10 ),(10 ,999 )]
        bucket_labels =['0-1Y','1-3Y','3-5Y','5-10Y','>10Y']
        bucket_data =[{'label':lbl ,'assets':0.0 ,'liabilities':0.0 }for lbl in bucket_labels ]
        from datetime import date 
        today =date .today ()
        for c in banco .contratos .all ()if banco else []:
            years =(c .fecha_vencimiento -today ).days /365.25 if c .fecha_vencimiento else 0 
            bi =0 
            for idx ,(lo ,hi )in enumerate (buckets ):
                if years >lo and years <=hi :
                    bi =idx 
                    break 
                if idx ==0 and years <=1 :
                    bi =0 
                    break 
            if c .activo_pasivo =='ACTIVO':
                bucket_data [bi ]['assets']+=c .nominal 
            else :
                bucket_data [bi ]['liabilities']+=c .nominal 
        for b in bucket_data :
            total =b ['assets']+b ['liabilities']
            b ['net_gap']=b ['assets']-b ['liabilities']
            b ['gap_pct']=b ['net_gap']/total *100 if total else 0 
        chart_buckets ={'labels':[b ['label']for b in bucket_data ],'assets':[b ['assets']for b in bucket_data ],'liabilities':[b ['liabilities']for b in bucket_data ],'gap':[b ['net_gap']for b in bucket_data ]}
        ctx .update ({'kpis':kpis ,'sot_info':sot_info ,'badges':badges ,'kris':kris ,'buckets':bucket_data ,'chart_buckets':chart_buckets })
        return ctx 
cartera_view =CarteraView .as_view ()
contratos_view =ContratosListView .as_view ()
aprobaciones_view =AprobacionesView .as_view ()