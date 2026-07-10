"""
Child-bot ConversationHandler holatlari.
"""

# --- Owner: do'kon admin qo'shish ---
ADD_ADMIN_ID = 1

# --- Kategoriya qo'shish/tahrirlash ---
CAT_ADD_NAME = 10
CAT_RENAME = 11

# --- Mahsulot qo'shish ---
PROD_CATEGORY, PROD_NAME, PROD_UNIT, PROD_BUY_PRICE, PROD_SELL_PRICE, PROD_PHOTO = range(20, 26)

# --- Sozlamalar: yetkazib berish narxi (km/so'm), karta, qo'llanma ---
SET_DELIVERY_PRICE_PER_KM = 30
SET_CARD_NUMBER = 31
SET_GUIDE_TEXT = 32
SET_ADMIN_CONTACT = 33
SET_SHOP_LOCATION = 34

# --- Mijoz: ism va telefon ---
ASK_NAME = 40
ASK_PHONE = 41

# --- Buyurtma berish: lokatsiya ---
ORDER_LOCATION = 50

# --- Mijoz: "Yetkazib berish narxi" tugmasi bosilganda lokatsiya so'rash ---
DELIVERY_CALC_LOCATION = 51

# --- Admin bilan aloqa ---
CONTACT_MESSAGE = 60

# --- Qidiruv ---
SEARCH_QUERY = 70
