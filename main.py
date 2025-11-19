import requests
import json
import tweepy
import time
import os
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from flask import Flask

app = Flask(__name__)
@app.route('/')
def home(): return "<h1>SAHA ICI VERI 2.0</h1>"
@app.route('/health')
def health(): return "OK", 200

# =====================================================
# AYARLAR
# =====================================================
CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
FUTBOL_API_KEY = os.environ.get("FUTBOL_API_KEY")

BASE_URL = "https://v3.football.api-sports.io"
VIP_LIGLER = [203, 2] 
VIP_TAKIMLAR = [33, 42, 49, 50, 40, 47, 529, 541, 505, 496]

def twittera_baglan():
    try:
        auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        client = tweepy.Client(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
        return api, client
    except: return None, None

# --- GÖRSEL MOTORU (HT ve FT için Dinamik) ---
def mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, durum_yazisi):
    img = Image.new('RGB', (800, 400), color=(15, 15, 25)) 
    d = ImageDraw.Draw(img)
    
    try: font_buyuk = ImageFont.truetype("arial.ttf", 60)
    except: font_buyuk = ImageFont.load_default()
    
    try: font_orta = ImageFont.truetype("arial.ttf", 40)
    except: font_orta = ImageFont.load_default()

    try: font_kucuk = ImageFont.truetype("arial.ttf", 25)
    except: font_kucuk = ImageFont.load_default()

    # Üst Başlık (DEVRE ARASI veya MAÇ SONUCU)
    d.text((400, 40), f"{lig.upper()} | {durum_yazisi}", fill=(255, 200, 0), anchor="mm", font=font_kucuk)
    
    # Skor
    d.text((400, 150), f"{skor_ev} - {skor_dep}", fill="white", anchor="mm", font=font_buyuk)
    d.text((200, 150), str(ev), fill="white", anchor="mm", font=font_orta)
    d.text((600, 150), str(dep), fill="white", anchor="mm", font=font_orta)
    
    if stats:
        stat_text = f"ŞUT: {stats.get('ev_sut',0)}-{stats.get('dep_sut',0)} | İSABET: {stats.get('ev_isabet',0)}-{stats.get('dep_isabet',0)}"
        d.text((400, 280), stat_text, fill=(200, 200, 200), anchor="mm", font=font_kucuk)
        
        stat_text2 = f"TOPLA OYNAMA: {stats.get('ev_top','?')}-{stats.get('dep_top','?')}"
        d.text((400, 320), stat_text2, fill=(200, 200, 200), anchor="mm", font=font_kucuk)

    dosya_adi = "mac_durumu.jpg"
    img.save(dosya_adi)
    return dosya_adi

def istatistikleri_getir(fixture_id):
    headers = {'x-apisports-key': FUTBOL_API_KEY}
    try:
        res = requests.get(f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}", headers=headers)
        data = res.json()
        if "response" in data and len(data['response']) == 2:
            ev = data['response'][0]['statistics']
            dep = data['response'][1]['statistics']
            def val(l, t):
                for i in l: 
                    if i['type'] == t: return i['value']
                return 0
            return {"ev_sut": val(ev, "Total Shots"), "dep_sut": val(dep, "Total Shots"), 
                    "ev_isabet": val(ev, "Shots on Goal"), "dep_isabet": val(dep, "Shots on Goal"), 
                    "ev_top": val(ev, "Ball Possession"), "dep_top": val(dep, "Ball Possession")}
    except: return None
    return None

def botu_calistir():
    if not FUTBOL_API_KEY: return
    api, client = twittera_baglan()
    if not api: return

    print(f"📡 ({datetime.now().strftime('%H:%M')}) Maçlar taranıyor...")
    bugun = datetime.today().strftime('%Y-%m-%d')
    headers = {'x-apisports-key': FUTBOL_API_KEY}
    
    try:
        response = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={"date": bugun})
        data = response.json()
    except: return

    if "response" in data:
        for mac in data['response']:
            fixture_id = mac['fixture']['id']
            lig_id = mac['league']['id']
            ev = mac['teams']['home']['name']
            dep = mac['teams']['away']['name']
            
            gonder = False
            if lig_id in VIP_LIGLER: gonder = True
            elif (mac['teams']['home']['id'] in VIP_TAKIMLAR) or (mac['teams']['away']['id'] in VIP_TAKIMLAR): gonder = True
            
            durum = mac['fixture']['status']['short']
            
            # --- HEM DEVRE ARASI (HT) HEM MAÇ SONU (FT) KONTROLÜ ---
            if gonder and (durum == "FT" or durum == "HT"):
                
                # Tweet başlığı belirle
                baslik = "MAÇ SONUCU 🏁" if durum == "FT" else "DEVRE ARASI ⏳"
                
                skor_ev = mac['goals']['home']
                skor_dep = mac['goals']['away']
                lig = mac['league']['name']
                
                stats = istatistikleri_getir(fixture_id)
                resim = mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, baslik)
                
                # --- HASHTAG STRATEJİSİ ---
                # Takım isimlerini birleştirip #GSvFB gibi tag yapıyoruz
                kisa_ev = ev.replace(" ", "")[:3].upper()
                kisa_dep = dep.replace(" ", "")[:3].upper()
                vs_tag = f"#{kisa_ev}v{kisa_dep}"
                
                tweet = f"{baslik} | {lig}\n\n"
                tweet += f"{ev} {skor_ev} - {skor_dep} {dep}\n\n"
                tweet += f"#Futbol {vs_tag} #{ev.replace(' ','')} #{dep.replace(' ','')}"
                
                try:
                    media = api.media_upload(resim)
                    client.create_tweet(text=tweet, media_ids=[media.media_id])
                    print(f"✅ TWEET ATILDI: {ev}-{dep} ({durum})")
                    time.sleep(300) # 5 dk bekle ki spam olmasın
                except Exception as e:
                    if "duplicate" in str(e).lower(): pass
                    else: print(f"Hata: {e}")

def bot_loop():
    print("🚀 BOT BAŞLADI")
    while True:
        try:
            botu_calistir()
            # KRİTİK AYAR: API KOTASI DOLMASIN DİYE 15 DAKİKA BEKLİYORUZ
            # Günde 96 İstek yapar, bedava kota 100. Tam yeter.
            print("💤 15 Dakika Mola...")
            time.sleep(900) 
        except Exception as e:
            print(f"Hata: {e}"); time.sleep(60)

if __name__ == "__main__":
    t = threading.Thread(target=bot_loop); t.daemon = True; t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))