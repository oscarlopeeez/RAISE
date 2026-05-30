from django .core .management .base import BaseCommand 
from irrbb_app .models import MarketCurve 
from irrbb_app .services .ecb_curve import fetch_ecb_curve 

class Command (BaseCommand ):
    help ='Fetch the latest EUR AAA-sovereigns spot yield curve from the ECB Data Portal'

    def handle (self ,*args ,**options ):
        self .stdout .write ('Fetching ECB yield curve...')
        try :
            ref_date ,points ,errors =fetch_ecb_curve ()
        except RuntimeError as e :
            self .stderr .write (self .style .ERROR (str (e )))
            return 
        if errors :
            for err in errors :
                self .stdout .write (self .style .WARNING (f'  warning: {err }'))
        mc =MarketCurve .objects .create (source =MarketCurve .SOURCE_ECB ,reference_date =ref_date ,currency ='EUR',tenors =points )
        self .stdout .write (self .style .SUCCESS (f'OK: MarketCurve#{mc .pk } reference_date={ref_date }, {len (points )} tenors'))
        for p in points :
            self .stdout .write (f"  {p ['label']:>4}  {p ['maturity_years']:>5.2f}Y  {p ['rate']*100 :>6.3f}%")