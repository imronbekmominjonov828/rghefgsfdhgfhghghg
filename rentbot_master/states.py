"""
ConversationHandler uchun holat (state) konstantalari (Master bot).
"""

# Mijoz: "Admin bilan aloqa" - xabar yozish
CONTACT_MESSAGE = 1

# Mijoz: to'lov cheki yuborish
PAYMENT_PHOTO = 2

# Mijoz: bot ma'lumotlarini to'ldirish formasi (ketma-ket so'raladi)
SETUP_SHOP_NAME, SETUP_TOKEN, SETUP_ADMIN_ID, SETUP_BOT_USERNAME = range(10, 14)

# Admin: tarif narxlarini o'zgartirish
TARIFF_TRIAL, TARIFF_MONTHLY, TARIFF_YEARLY = range(20, 23)

# Admin: karta raqamini o'zgartirish
CARD_NUMBER = 25
