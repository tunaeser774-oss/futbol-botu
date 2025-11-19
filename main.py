import requests
import json
import tweepy
import time
import os
import threading
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from flask import Flask

# =====================================================
# 1. WEB SİTESİ AYARLARI (Render Port Hatası Almasın Diye)
# =====================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>SAHA ICI VERI BOTU CALISIYOR</h1><p>Sistem Aktif ve Nöbette.</p>"

@app.route('/health')
def health():
    return "OK", 200

# =====================================================
# 2. AYARLAR VE ŞİFRELER (Render Environment'tan Çeker)
# =====================================================
CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
FUTBOL_API_KEY = os.environ.get("FUTBOL_API_KEY")

BASE_URL = "https://v3.football.api-sports.io"

# VIP LİGLER LİSTESİ (Genişletilmiş)
# 203: Süper Lig | 2: Şampiyonlar Ligi
# 10: Hazırlık Maçları (Friendlies) -> BUGÜN İÇİN EKLENDİ
# 1: Dünya Kupası | 4: Euro Elemeleri | 5: Uluslar Ligi
VIP_LIGLER = [203, 2, 10, 1, 4, 5] 

# VIP TAKIMLAR (Büyük Takımların Hazırlık Maçlarını Kaçırmamak İçin)
VIP_TAKIMLAR = [33, 42, 49, 50, 40, 47, 529, 541, 505, 496, 645, 600, 611, 597] # Big 6 + TR Büyükler

def twittera_baglan():
    try:
        # v1.1 API (Medya Yükleme İçin)
        auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)
        
        # v2 API (Tweet Atma İçin)
        client = tweepy.Client(
            consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
        )
        return api, client
    except:
        return None, None

# --- GÖRSEL OLUŞTURMA MOTORU ---
def mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, durum_yazisi):
    # Arka Plan (Koyu Lacivert)
    img = Image.new('RGB', (800, 400), color=(15, 20, 35)) 
    d = ImageDraw.Draw(img)
    
    # Font Ayarları (Sunucuda font yoksa default kullan)
    try:
        font_buyuk = ImageFont.truetype("arial.ttf", 60)
        font_orta = ImageFont.truetype("arial.ttf", 40)
        font_kucuk = ImageFont.truetype("arial.ttf", 25)
    except:
        font_buyuk = ImageFont.load_default()
        font_orta = ImageFont.load_default()
        font_kucuk = ImageFont.load_default()

    # Başlık (Lig ve Durum)
    baslik = f"{str(lig).upper()} | {durum_yazisi}"
    d.text((400, 40), baslik, fill=(255, 200, 0), anchor="mm", font=font_kucuk) # Sarı Başlık
    
    # Skor
    skor_text = f"{skor_ev} - {skor_dep}"
    d.text((400, 150), skor_text, fill="white", anchor="mm", font=font_buyuk)
    
    # Takımlar
    d.text((200, 150), str(ev), fill="white", anchor="mm", font=font_orta)
    d.text((600, 150), str(dep), fill="white", anchor="mm", font=font_orta)
    
    # İstatistikleri Yaz
    if stats:
        stat_text = f"ŞUT: {stats.get('ev_sut',0)}-{stats.get('dep_sut',0)}  |  İSABET: {stats.get('ev_isabet',0)}-{stats.get('dep_isabet',0)}"
        d.text((400, 280), stat_text, fill=(200, 200, 200), anchor="mm", font=font_kucuk)
        
        stat_text2 = f"TOPLA OYNAMA: {stats.get('ev_top','?')}-{stats.get('dep_top','?')}"
        d.text((400, 320), stat_text2, fill=(200, 200, 200), anchor="mm", font=font_kucuk)

    dosya_adi = "mac_sonucu.jpg"
    img.save(dosya_adi)
    return dosya_adi

# --- İSTATİSTİK ÇEKME ---
def istatistikleri_getir(fixture_id):
    headers = {'x-apisports-key': FUTBOL_API_KEY}
    try:
        res = requests.get(f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}", headers=headers)
        data = res.json()
        if "response" in data and len(data['response']) == 2:
            ev_stats = data['response'][0]['statistics']
            dep_stats = data['response'][1]['statistics']
            
            def val(liste, tip):
                for item in liste:
                    if item['type'] == tip: return item['value']
                return 0

            return {
                "ev_sut": val(ev_stats, "Total Shots"), 
                "dep_sut": val(dep_stats, "Total Shots"),
                "ev_isabet": val(ev_stats, "Shots on Goal"), 
                "dep_isabet": val(dep_stats, "Shots on Goal"),
                "ev_top": val(ev_stats, "Ball Possession"), 
                "dep_top": val(dep_stats, "Ball Possession")
            }
    except: return None
    return None

# --- BOT MANTIĞI ---
def botu_calistir():
    if not FUTBOL_API_KEY: return
    api, client = twittera_baglan()
    if not api: return

    print(f"📡 ({datetime.now().strftime('%H:%M')}) Maçlar taranıyor...")
    
    # BUGÜNÜN TARİHİ (Normal Mod)
    bugun = datetime.today().strftime('%Y-%m-%d')
    
    # TEST MODU: Eğer bugün maç yoksa ve dünü denemek istersen alt satırın başındaki # işaretini sil:
    # bugun = "2025-11-18" 

    headers = {'x-apisports-key': FUTBOL_API_KEY}
    
    try:
        response = requests.get(f"{BASE_URL}/fixtures", headers=headers, params={"date": bugun})
        data = response.json()
    except: return

    if "response" in data:
        for mac in data['response']:
            fixture_id = mac['fixture']['id']
            lig_id = mac['league']['id']
            ev_id = mac['teams']['home']['id']
            dep_id = mac['teams']['away']['id']
            
            # Filtreleme (VIP Ligler veya VIP Takımlar)
            gonder = False
            if lig_id in VIP_LIGLER: gonder = True
            elif (ev_id in VIP_TAKIMLAR) or (dep_id in VIP_TAKIMLAR): gonder = True
            
            durum = mac['fixture']['status']['short']
            
            # HEM MAÇ SONU (FT) HEM DEVRE ARASI (HT) KONTROLÜ
            if gonder and (durum == "FT" or durum == "HT"):
                
                baslik = "MAÇ SONUCU 🏁" if durum == "FT" else "DEVRE ARASI ⏳"
                
                ev = mac['teams']['home']['name']
                dep = mac['teams']['away']['name']
                skor_ev = mac['goals']['home']
                skor_dep = mac['goals']['away']
                lig = mac['league']['name']
                
                # İstatistikleri al ve resmi çiz
                stats = istatistikleri_getir(fixture_id)
                resim_yolu = mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats, baslik)
                
                # Hashtag Oluşturma (#TURvWAL gibi)
                tag1 = ev.replace(" ", "")[:3].upper()
                tag2 = dep.replace(" ", "")[:3].upper()
                vs_tag = f"#{tag1}v{tag2}"
                
                tweet = f"{baslik} | {lig}\n\n"
                tweet += f"{ev} {skor_ev} - {skor_dep} {dep}\n\n"
                tweet += f"#Futbol {vs_tag} #{ev.replace(' ','')} #{dep.replace(' ','')}"
                
                print(f"🐦 Tweet Hazır: {ev} vs {dep} ({durum})")
                
                try:
                    media = api.media_upload(resim_yolu)
                    client.create_tweet(text=tweet, media_ids=[media.media_id])
                    print("✅ TWEET BAŞARIYLA ATILDI!")
                    time.sleep(300) # Aynı maçı spamlamamak için 5 dk bekle
                except Exception as e:
                    if "duplicate" in str(e).lower(): pass # Zaten atılmışsa sorun yok
                    else: print(f"Hata: {e}")

# --- DÖNGÜ ---
def bot_loop():
    print("🚀 BOT BAŞLADI (15 DK ARAYLA ÇALIŞACAK)")
    while True:
        try:
            botu_calistir()
            # API KOTASI İÇİN 15 DAKİKA (900 sn) BEKLEME SÜRESİ
            print("💤 15 Dakika Mola...")
            time.sleep(900) 
        except Exception as e:
            print(f"Döngü Hatası: {e}")
            time.sleep(60)

# =====================================================
# 3. BAŞLATMA (Thread + Flask)
# =====================================================
if __name__ == "__main__":
    # Botu Arka Planda Başlat
    t = threading.Thread(target=bot_loop)
    t.daemon = True
    t.start()
    
    # Web Sitesini Başlat (Render İçin)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)