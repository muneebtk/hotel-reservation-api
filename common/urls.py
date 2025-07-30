from django.urls import path
from common.views import health_check, PaymentStatusView, WalletPaymentStatusView

urlpatterns = [

    path('health-check', health_check, name='health-check'),
    path('payment-status', PaymentStatusView.as_view(), name='payment_status'),
    path('wallet-payment-status', WalletPaymentStatusView.as_view(), name='payment_status')
    
    
]



