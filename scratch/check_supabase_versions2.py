import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv("D:/CafeScraper/.env")
SUPABASE_URL = "https://suwinftalfgybvrnzruz.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
res = supabase.table("app_versions").select("*").in_("product_id", ["CafeCrawler", "EventStats", "AutoComment"]).order("id", desc=True).limit(10).execute()
for row in res.data:
    print(row['product_id'], row['version'])
