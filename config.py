import os
from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY", "xai-ApoeBxVHEbedVEC8U1wI0j4Kyq842XRyxCFposhTe9DisPG1JwvqIrtay6qiWrhhdJq2rVb8EDHqvkjZ")
GROK_MODEL   = os.getenv("GROK_MODEL", "grok-imagine-image")   # change via env var if needed

WP_BASE_URL = os.getenv("WP_BASE_URL", "https://motasport.com")
WP_USERNAME = os.getenv("WP_USERNAME", "admin")
WP_APP_PASS = os.getenv("WP_APP_PASS", "O0kK pqnZ 6GCx SoJN 4Ru0 YLKh")

GARMENT_IMAGES = [
    "https://motasport.com/wp-content/uploads/2026/03/colar_front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/fabric.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/front.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/pocket.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/sleeve.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/tidy.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/back.jpeg",
    "https://motasport.com/wp-content/uploads/2026/03/colar_back.jpeg",
]
GARMENT_LABELS = [
    "collar_front", "fabric", "front", "pocket",
    "sleeve", "tidy", "back", "collar_back",
]

REQUIRED_COLUMNS = {"pattern_prompt", "title", "description"}

WC_COLUMNS = [
    "ID", "Type", "SKU", "GTIN, UPC, EAN, or ISBN", "Name",
    "Published", "Is featured?", "Visibility in catalog",
    "Short description", "Description",
    "Date sale price starts", "Date sale price ends",
    "Tax status", "Tax class", "In stock?", "Stock",
    "Low stock amount", "Backorders allowed?", "Sold individually?",
    "Weight (kg)", "Length (cm)", "Width (cm)", "Height (cm)",
    "Allow customer reviews?", "Purchase note",
    "Sale price", "Regular price",
    "Categories", "Tags", "Shipping class",
    "Images",
    "Download limit", "Download expiry days",
    "Parent", "Grouped products", "Upsells", "Cross-sells",
    "External URL", "Button text", "Position",
    "WCPA Forms", "Brands", "Product URL",
    "Prompt",
]

WC_DEFAULTS = {
    "Type": "simple", "Published": "1", "Is featured?": "0",
    "Visibility in catalog": "visible", "Tax status": "taxable",
    "Tax class": "", "In stock?": "1", "Stock": "",
    "Low stock amount": "", "Backorders allowed?": "0",
    "Sold individually?": "0", "Weight (kg)": "", "Length (cm)": "",
    "Width (cm)": "", "Height (cm)": "", "Allow customer reviews?": "1",
    "Purchase note": "", "Sale price": "", "Regular price": "32.99",
    "Categories": "Urban Edge", "Tags": "", "Shipping class": "",
    "Download limit": "", "Download expiry days": "", "Parent": "",
    "Grouped products": "", "Upsells": "", "Cross-sells": "",
    "External URL": "", "Button text": "", "Position": "0",
    "WCPA Forms": "0", "Brands": "", "GTIN, UPC, EAN, or ISBN": "",
    "Short description": "", "Date sale price starts": "",
    "Date sale price ends": "",
}

# On VPS these are real directories, not /tmp
UPLOAD_FOLDER  = os.getenv("UPLOAD_FOLDER",  "/tmp/uploads")
OUTPUT_FOLDER  = os.getenv("OUTPUT_FOLDER",  "/tmp/outputs")
GARMENT_FOLDER = os.getenv("GARMENT_FOLDER", "/tmp/garments")
MAX_CONTENT_MB = 10
