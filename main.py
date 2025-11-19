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
# 1. WEB SİTESİ AYARLARI (RENDER'I KANDIRMA)
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>BOT CALISIYOR!</h1><p>Merak etme, Saha Ici Veri arka planda isliyor.</p>"

# =====================================================
# 2. AYARLAR VE ŞİFRELER
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
    except:
        return None, None

def mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats):
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

    d.text((400, 30), str(lig).upper(), fill=(200, 200, 200), anchor="mm", font=font_kucuk)
    d.text((400, 150), f"{skor_ev} - {skor_dep}", fill=(255, 255, 0), anchor="mm", font=font_buyuk)
    d.text((200, 150), str(ev), fill="white", anchor="mm", font=font_orta)
    d.text((600, 150), str(dep), fill="white", anchor="mm", font=font_orta)
    
    if stats:
        stat_text = f"SUT: {stats.get('ev_sut',0)} - {stats.get('dep_sut',0)}  |  ISABET: {stats.get('ev_isabet',0)} - {stats.get('dep_isabet',0)}"
        d.text((400, 280), stat_text, fill="white", anchor="mm", font=font_kucuk)

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

# --- ASIL BOT DÖNGÜSÜ (Arka Planda Çalışacak) ---
def bot_loop():
    print("🚀 FUTBOL BOTU ARKA PLANDA BAŞLADI!")
    while True:
        try:
            print("📡 Tarama yapılıyor...")
            if not FUTBOL_API_KEY or not CONSUMER_KEY:
                print("⚠️ Şifreler yok, bekleniyor...")
                time.sleep(60)
                continue

            api, client = twittera_baglan()
            if not api: 
                time.sleep(60); continue

            bugun = datetime.today().strftime('%Y-%m-%d')
            headers = {'x-apisports-key': FUTBOL_API_KEY}
            
            try:
                response = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={"date": bugun})
                data = response.json()
                
                if "response" in data:
                    for mac in data['response']:
                        fixture_id = mac['fixture']['id']
                        lig_id = mac['league']['id']
                        ev_id = mac['teams']['home']['id']
                        dep_id = mac['teams']['away']['id']
                        
                        gonder = False
                        if lig_id in VIP_LIGLER: gonder = True
                        elif (ev_id in VIP_TAKIMLAR) or (dep_id in VIP_TAKIMLAR): gonder = True
                        
                        if gonder and mac['fixture']['status']['short'] == "FT":
                            ev = mac['teams']['home']['name']
                            dep = mac['teams']['away']['name']
                            skor_ev = mac['goals']['home']
                            skor_dep = mac['goals']['away']
                            lig = mac['league']['name']
                            
                            stats = istatistikleri_getir(fixture_id)
                            resim_yolu = mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats)
                            tweet = f"🏁 MAÇ SONUCU | {lig}\n\n{ev} {skor_ev} - {skor_dep} {dep}\n\n#Futbol #{ev.replace(' ','')} #{dep.replace(' ','')}"
                            
                            try:
                                media = api.media_upload(resim_yolu)
                                client.create_tweet(text=tweet, media_ids=[media.media_id])
                                print(f"✅ TWEET ATILDI: {ev}-{dep}")
                                time.sleep(20)
                            except Exception as e:
                                if "duplicate" in str(e).lower(): pass
                                else: print(f"Hata: {e}")
            except Exception as e:
                print(f"API Hatası: {e}")

            print("✅ Tur bitti. 10 dakika mola...")
            time.sleep(600) # 10 Dakika bekle
            
        except Exception as e:
            print(f"Döngü Hatası: {e}")
            time.sleep(60)

# =====================================================
# 3. BAŞLATMA NOKTASI (Önce Botu Başlat, Sonra Siteyi Aç)
# =====================================================
if __name__ == "__main__":
    # 1. Botu Arka Plana At
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True # Ana program kapanırsa bu da kapansın
    thread.start()
    
    # 2. Web Sitesini Başlat (Render bunu görecek ve mutlu olacak)
    # Port ayarı Render için çok kritiktir
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)