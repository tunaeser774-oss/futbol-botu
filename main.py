import requests
import json
import tweepy
import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# =====================================================
# 1. GÜVENLİ AYARLAR (Şifreler Render'dan Gelecek)
# =====================================================
# Bilgisayarında çalıştırırken hata verirse, şifreleri Environment'a eklemedin demektir.
CONSUMER_KEY = os.environ.get("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET")
ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

FUTBOL_API_KEY = os.environ.get("FUTBOL_API_KEY")

BASE_URL = "https://v3.football.api-sports.io"

# VIP FİLTRELER (Süper Lig, Şampiyonlar Ligi ve Dev Takımlar)
VIP_LIGLER = [203, 2] 
VIP_TAKIMLAR = [33, 42, 49, 50, 40, 47, 529, 541, 505, 496]

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
    except Exception as e:
        print(f"Twitter Bağlantı Hatası: {e}")
        return None, None

# --- RESİM OLUŞTURMA MOTORU ---
def mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats):
    # 800x400 Siyah Zemin
    img = Image.new('RGB', (800, 400), color=(20, 20, 30)) 
    d = ImageDraw.Draw(img)
    
    # Font Ayarları (Sunucuda arial olmayabilir, default kullanırız)
    try:
        font_buyuk = ImageFont.truetype("arial.ttf", 60)
        font_orta = ImageFont.truetype("arial.ttf", 40)
        font_kucuk = ImageFont.truetype("arial.ttf", 25)
    except:
        # Eğer font yoksa varsayılan dandik fontu kullan (Hata vermez)
        font_buyuk = ImageFont.load_default()
        font_orta = ImageFont.load_default()
        font_kucuk = ImageFont.load_default()

    # Yazılar
    d.text((400, 30), str(lig).upper(), fill=(200, 200, 200), anchor="mm", font=font_kucuk)
    d.text((400, 150), f"{skor_ev} - {skor_dep}", fill=(255, 255, 0), anchor="mm", font=font_buyuk)
    d.text((200, 150), str(ev), fill="white", anchor="mm", font=font_orta)
    d.text((600, 150), str(dep), fill="white", anchor="mm", font=font_orta)
    
    if stats:
        stat_text = f"SUT: {stats.get('ev_sut',0)} - {stats.get('dep_sut',0)}  |  ISABET: {stats.get('ev_isabet',0)} - {stats.get('dep_isabet',0)}"
        d.text((400, 280), stat_text, fill="white", anchor="mm", font=font_kucuk)
        
        stat_text2 = f"TOPLA OYNAMA: {stats.get('ev_top','?')} - {stats.get('dep_top','?')}"
        d.text((400, 320), stat_text2, fill="white", anchor="mm", font=font_kucuk)

    dosya_adi = "mac_sonucu.jpg"
    img.save(dosya_adi)
    return dosya_adi

# --- İSTATİSTİK ÇEKME ---
def istatistikleri_getir(fixture_id):
    headers = {'x-apisports-key': FUTBOL_API_KEY}
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        if "response" in data and len(data['response']) == 2:
            ev_stats = data['response'][0]['statistics']
            dep_stats = data['response'][1]['statistics']
            
            def val(liste, tip):
                for item in liste:
                    if item['type'] == tip: return item['value']
                return 0

            return {
                "ev_sut": val(ev_stats, "Total Shots"), "dep_sut": val(dep_stats, "Total Shots"),
                "ev_isabet": val(ev_stats, "Shots on Goal"), "dep_isabet": val(dep_stats, "Shots on Goal"),
                "ev_top": val(ev_stats, "Ball Possession"), "dep_top": val(dep_stats, "Ball Possession")
            }
    except: return None
    return None

# --- ANA ÇALIŞMA MANTIĞI ---
def botu_calistir():
    if not FUTBOL_API_KEY or not CONSUMER_KEY:
        print("⚠️ HATA: Şifreler Environment'tan çekilemedi! Render ayarlarını kontrol et.")
        return

    api, client = twittera_baglan()
    if not api: return

    print("📡 Maçlar taranıyor...")
    bugun = datetime.today().strftime('%Y-%m-%d')
    # TEST İÇİN GEREKİRSE BURAYI AÇ: bugun = "2024-03-10"

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
            
            # Filtreleme
            gonder = False
            if lig_id in VIP_LIGLER: gonder = True
            elif (ev_id in VIP_TAKIMLAR) or (dep_id in VIP_TAKIMLAR): gonder = True
            
            # Maç Bitmişse (FT)
            if gonder and mac['fixture']['status']['short'] == "FT":
                ev = mac['teams']['home']['name']
                dep = mac['teams']['away']['name']
                skor_ev = mac['goals']['home']
                skor_dep = mac['goals']['away']
                lig = mac['league']['name']
                
                # İstatistik ve Resim
                stats = istatistikleri_getir(fixture_id)
                resim_yolu = mac_karti_olustur(ev, dep, skor_ev, skor_dep, lig, stats)
                
                tweet = f"🏁 MAÇ SONUCU | {lig}\n\n{ev} {skor_ev} - {skor_dep} {dep}\n\n#Futbol #{ev.replace(' ','')} #{dep.replace(' ','')}"
                
                print(f"🐦 Görsel Yükleniyor: {ev} vs {dep}")
                
                try:
                    # Resmi Yükle ve Tweet At
                    media = api.media_upload(resim_yolu)
                    client.create_tweet(text=tweet, media_ids=[media.media_id])
                    print("✅ TWEET ATILDI!")
                    time.sleep(15)
                except Exception as e:
                    if "duplicate" in str(e).lower(): 
                        print(f"⚠️ {ev}-{dep} zaten atılmış.")
                    else: 
                        print(f"❌ Hata: {e}")

# --- 7/24 SONSUZ DÖNGÜ ---
if __name__ == "__main__":
    print("🚀 GÜVENLİ FUTBOL BOTU BAŞLATILDI (CLOUD MODE)")
    while True:
        try:
            botu_calistir()
            print("✅ Tur bitti. 10 dakika mola...")
            time.sleep(600) # 10 Dakika bekle
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(60)