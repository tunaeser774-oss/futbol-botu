import requests
import json
import tweepy
import time
import os
import threading
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from flask import Flask

# =====================================================
# 1. WEB SİTESİ AYARLARI
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>SAHA ICI VERI BOTU CALISIYOR</h1><p>Sistem Aktif.</p>"

@app.route('/health')
def health():
    return "OK", 200

# =====================================================
# 2. AYARLAR
# =====================================================
CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
FUTBOL_API_KEY = os.environ.get("FUTBOL_API_KEY")

BASE_URL = "https://v3.football.api-sports.io"
VIP_LIGLER = [203, 2, 10, 1, 4, 5] 
VIP_TAKIMLAR = [33, 42, 49, 50, 40, 47, 529, 541, 505, 496]

def twittera_baglan():
    try:
        auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        client = tweepy.Client(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
        return api, client
    except:
        return None, None

def mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, durum_yazisi):
    img = Image.new('RGB', (800, 400), color=(20, 20, 30)) 
    d = ImageDraw.Draw(img)
    try:
        font_buyuk = ImageFont.truetype("arial.ttf", 60)
        font_orta = ImageFont.truetype("arial.ttf", 40)
        font_kucuk = ImageFont.truetype("arial.ttf", 25)
    except:
        font_buyuk = ImageFont.load_default()
        font_orta = ImageFont.load_default()
        font_kucuk = ImageFont.load_default()

    baslik = f"{str(lig).upper()} | {durum_yazisi}"
    d.text((400, 40), baslik, fill=(255, 200, 0), anchor="mm", font=font_kucuk)
    d.text((400, 150), f"{skor_ev} - {skor_dep}", fill="white", anchor="mm", font=font_buyuk)
    d.text((200, 150), str(ev), fill="white", anchor="mm", font=font_orta)
    d.text((600, 150), str(dep), fill="white", anchor="mm", font=font_orta)
    
    if stats:
        stat_text = f"SUT: {stats.get('ev_sut',0)}-{stats.get('dep_sut',0)}  |  ISABET: {stats.get('ev_isabet',0)}-{stats.get('dep_isabet',0)}"
        d.text((400, 280), stat_text, fill="white", anchor="mm", font=font_kucuk)
        stat_text2 = f"TOPLA OYNAMA: {stats.get('ev_top','?')}-{stats.get('dep_top','?')}"
        d.text((400, 320), stat_text2, fill="white", anchor="mm", font=font_kucuk)

    dosya_adi = "mac_sonucu.jpg"
    img.save(dosya_adi)
    return dosya_adi

def istatistikleri_getir(fixture_id):
    headers = {'x-apisports-key': FUTBOL_API_KEY}
    try:
        res = requests.get(f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}", headers=headers)
        data = res.json()
        if "response" in data and len(data['response']) == 2:
            ev_stats = data['response'][0]['statistics']
            dep_stats = data['response'][1]['statistics']
            def val(l, t):
                for i in l: 
                    if i['type'] == t: return i['value']
                return 0
            return {"ev_sut": val(ev_stats, "Total Shots"), "dep_sut": val(dep_stats, "Total Shots"), "ev_isabet": val(ev_stats, "Shots on Goal"), "dep_isabet": val(dep_stats, "Shots on Goal"), "ev_top": val(ev_stats, "Ball Possession"), "dep_top": val(dep_stats, "Ball Possession")}
    except: return None
    return None

def botu_calistir():
    if not FUTBOL_API_KEY: return
    api, client = twittera_baglan()
    if not api: return

    print(f"📡 ({datetime.now().strftime('%H:%M')}) Maçlar taranıyor...")
    
    # BUGÜNÜN TARİHİ
    bugun = datetime.today().strftime('%Y-%m-%d')
    # TEST İÇİN: bugun = "2025-11-18"

    headers = {'x-apisports-key': FUTBOL_API_KEY}
    try:
        response = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={"date": bugun})
        data = response.json()
        
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
                
                if gonder and (durum == "FT" or durum == "HT"):
                    baslik = "MAÇ SONUCU 🏁" if durum == "FT" else "DEVRE ARASI ⏳"
                    skor_ev = mac['goals']['home']
                    skor_dep = mac['goals']['away']
                    lig = mac['league']['name']
                    
                    stats = istatistikleri_getir(fixture_id)
                    resim_yolu = mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, baslik)
                    
                    tag1 = ev.replace(" ", "")[:3].upper()
                    tag2 = dep.replace(" ", "")[:3].upper()
                    vs_tag = f"#{tag1}v{tag2}"
                    
                    tweet = f"{baslik} | {lig}\n\n{ev} {skor_ev} - {skor_dep} {dep}\n\n#Futbol {vs_tag} #{ev.replace(' ','')} #{dep.replace(' ','')}"
                    
                    print(f"🐦 Tweet Hazır: {ev} vs {dep}")
                    try:
                        media = api.media_upload(resim_yolu)
                        client.create_tweet(text=tweet, media_ids=[media.media_id])
                        print("✅ TWEET ATILDI!")
                        time.sleep(300)
                    except Exception as e:
                        if "duplicate" in str(e).lower(): pass
                        else: print(f"Hata: {e}")
    except Exception as e:
        print(f"API Hatası: {e}")

def bot_loop():
    print("🚀 FUTBOL BOTU ARKA PLANDA BAŞLADI!")
    while True:
        try:
            botu_calistir()
            print("💤 15 Dakika Mola...")
            time.sleep(900) 
        except Exception as e:
            print(f"Döngü Hatası: {e}")
            time.sleep(60)

# =====================================================
# 🚀 ÖNEMLİ DEĞİŞİKLİK BURADA
# =====================================================
# Botu başlatma emrini 'if __name__' dışına çıkardık.
# Böylece Gunicorn dosyayı okuduğu an bot çalışmaya başlar.

t = threading.Thread(target=bot_loop)
t.daemon = True
t.start()

if __name__ == "__main__":
    # Bu kısım sadece yerel testler içindir, Render burayı görmezden gelir
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))