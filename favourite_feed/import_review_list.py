from favourite_feed.database import connect_database, setup_database
from favourite_feed.discovery import setup

ROWS = """60611701 MpGemsIndia IN 4.9 81
61104361 InfinityCabochons IN 4.94 123
61308999 UniqueAlfizaGems IN 4.59 26
61617277 AfghanGemsSupply IN 5 31
61630163 antiquartzgems IN 4.78 62
62022563 Esagemstone IN 4.92 166
62520644 GetChristmasGifts IN 4.81 200
62582531 ANJANEYAGEMSGIFTS IN 4.91 275
5400076 MyGlitterStuff US 4.97 2118
6232492 ALIFINTERNATIONAL786 IN 4.69 1269
8647667 ABCJewelryMart IN 4.74 3348
9533221 AceGemstones IN 4.71 2557
9609438 BlazeNGems US 4.89 435
10599172 ShungitArtCabochons US 4.92 7639
10743095 JBCBeads US 4.93 23949
11028025 GemsDiamondsBySHIKHA IN 4.83 6367
11185737 aDashofHappy US 4.95 2162
11658652 Gembeadstore US 4.84 701
11979048 SGPSHOP IN 4.92 1387
12305092 ICanMakeThatNow US 4.87 4946
12793272 kcinternational IN 4.51 170
12845287 mooncatcrystals US 4.96 798
13272335 SeekGems US 4.96 535
13428797 ColoradoGemworks US 4.98 3559
13443165 gomesgems IN 4.73 162
14068410 Rarekindstones IN 4.91 306
14456217 AkstarGems US 4.78 1964
14753557 Artexpogemstones IN 4.89 400
14831969 RoyalGemPalace IN 4.93 1576
15294552 MIXGEMSTONEUSA IN 4.5 696
16399684 NoorGemsGB IN 4.89 1133
16720885 StoneAgeLapidary ID 4.7 1914
17565038 GemMartUS IN 4.51 2042
18185750 TheGemsTerra IN 4.71 2587
19151362 SilverSeaJewels1 IN 4.65 943
19581439 FQZSHOP IN 4.93 286
20087969 BrightGreenGems IN 4.72 854
20485941 GemsFactorybySiraj IN 4.62 3350
20557205 CabochonGemsJewelry IN 4.79 113
21543215 SierraCanyonGems US 4.96 494
21559694 NewGemsBeads IN 4.64 354
22227036 BerkahJayaStone ID 4.94 156
22504699 GrGemsWork IN 4.87 2672
22636130 ASGemsAndJewels IN 4.67 153
23765529 VillageVibe US 4.91 4934
23893536 ZaidgemsTreasures IN 4.62 448
24068448 Dangemsco US 4.88 963
24319621 MaxBriteGems US 4.97 167
25048974 Gemsexport IN 4.54 72
25845881 GempiresIN IN 4.8 769
27480519 MOHAMMEDGEMSShop IN 4.66 1022
28086079 GemsByAlina IN 4.72 352
28282901 PopeGems IN 4.82 443
28599824 Gemstonejpr IN 4.7 6581
29090474 gems2cre8 US 4.95 9865
30444908 Cabochonsandcuts IN 4.84 142
30790137 BLUESTERGEMSTONEJEW IN 4.91 220
32584085 ShayaanWorld IN 5 59
33145926 GalaxyCrystalGems IN 4.76 72
34637455 UniqueStoneIN IN 4.66 297
34972909 AbstractRockShop US 4.99 107
38077675 Yuvaanbeadsfindings IN 4.84 499
40327642 shivanjaliplusgems IN 4.84 271
43416057 Rockgemsandjewelry IN 4.85 134
45231600 Houseofstoneshop IN 4.74 912
45350032 LabradoriteIN IN 4.64 457
47192717 Ziaragemsshop IN 4.85 221
48056329 BILALGEMSSHOP IN 4.62 315
54874770 SivaMinerallover ID 4.83 63
60022543 MinistryofGems IN 4.78 147
61105620 NazJewelryLLC IN 4.53 210
61987032 ArisGemsIn IN 4.85 172
62228588 dakshexport IN 4.97 557
7632577 SequoiasRoots US 4.98 10938
13969798 ckpsupplies US 4.95 3678
22245206 TACGEMS IN 4.79 1475
25504470 GemsbyGanibaba IN 4.72 1458
36928478 SparklegemsIndia IN 4.84 254
60182538 KHADIJAGEMSJEWELRY IN 4.97 49
60329323 DRUZYGEMSDesign IN 4.73 671"""

def main():
    setup_database()
    added=0
    with connect_database() as conn:
        setup(conn)
        for line in ROWS.splitlines():
            sid,name,country,rating,reviews=line.split()
            result=conn.execute("""INSERT OR IGNORE INTO discovery_shops
                (shop_id,name,country,rating,reviews,evidence)
                SELECT ?,?,?,?,?,'Needs checking'
                WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=? OR lower(shop_name)=lower(?))""",
                (int(sid),name,country,float(rating),int(reviews),int(sid),name))
            added+=result.rowcount
        pending=conn.execute("SELECT COUNT(*) FROM discovery_shops d WHERE status='pending' AND NOT EXISTS (SELECT 1 FROM monitored_shops m WHERE m.shop_id=d.shop_id)").fetchone()[0]
    print(f"Imported {added} shops; {pending} shops awaiting review.")

if __name__=="__main__":
    main()
