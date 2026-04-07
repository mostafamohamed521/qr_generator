import qrcode
from io import BytesIO
import base64

class QRGenerator:
    @staticmethod
    def generate_qr(data, size=300, color='black', bg_color='white'):
        """Generate QR code and return as base64"""
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color=color, back_color=bg_color)
        
        # Resize if needed
        if size != 300:
            img = img.resize((size, size))
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{image_base64}"
    
    @staticmethod
    def generate_vcard(data):
        """Generate VCard contact"""
        vcard = f"""BEGIN:VCARD
VERSION:3.0
FN:{data.get('first_name', '')} {data.get('last_name', '')}
N:{data.get('last_name', '')};{data.get('first_name', '')};;;
ORG:{data.get('organization', '')}
TITLE:{data.get('title', '')}
TEL;TYPE=WORK,VOICE:{data.get('phone', '')}
TEL;TYPE=CELL:{data.get('mobile', '')}
EMAIL:{data.get('email', '')}
URL:{data.get('website', '')}
ADR;TYPE=WORK:;;{data.get('address', '')};;;;
END:VCARD"""
        return vcard
    
    @staticmethod
    def generate_wifi_qr(ssid, password, encryption='WPA'):
        """Generate WiFi QR code"""
        if encryption == 'nopass':
            return f"WIFI:S:{ssid};;"
        return f"WIFI:T:{encryption};S:{ssid};P:{password};;"
    
    @staticmethod
    def generate_sms_qr(phone, message):
        """Generate SMS QR code"""
        return f"SMSTO:{phone}:{message}"
    
    @staticmethod
    def generate_email_qr(email, subject, body):
        """Generate Email QR code"""
        return f"MATMSG:TO:{email};SUB:{subject};BODY:{body};"