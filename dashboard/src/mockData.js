// ── Mock data — simulates detection_engine.py output ────────────────────────
// All coordinates, speeds, and scores are realistic maritime data

export const RISK_ZONES = [
  {
    id: "hormuz", name: "Détroit d'Ormuz", type: "DÉTROIT", level: "EXTREME",
    polygon: [[26,55],[26,60],[23,60],[23,55]],
    center: [25, 57.5],
  },
  {
    id: "aden", name: "Golfe d'Aden", type: "PIRATERIE", level: "EXTREME",
    polygon: [[13,43],[13,51],[11,51],[11,43]],
    center: [12, 47],
  },
  {
    id: "malacca", name: "Détroit de Malacca", type: "PIRATERIE", level: "ELEVE",
    polygon: [[6,99],[6,104],[1,104],[1,99]],
    center: [3.5, 101.5],
  },
  {
    id: "bab", name: "Bab-el-Mandeb", type: "DÉTROIT", level: "ELEVE",
    polygon: [[13,43],[13,45],[11.5,45],[11.5,43]],
    center: [12.2, 44],
  },
  {
    id: "med_est", name: "Méditerranée Orientale", type: "SURVEILLANCE", level: "MODERE",
    polygon: [[38,24],[38,36],[32,36],[32,24]],
    center: [35, 30],
  },
  {
    id: "channel", name: "Manche", type: "TRAFIC DENSE", level: "SURVEILLE",
    polygon: [[52,-5],[52,2],[49,2],[49,-5]],
    center: [50.5, -1.5],
  },
];

const ALL_SHIPS = [
  // Tankers
  { mmsi:"227001000", name:"ARCTIC VOYAGER",     type:"Tanker",          flag:"France",           length:330, year_built:2008, gross_tonnage:150000, destination:"Marseille",   lat_ais:26.3, lon_ais:56.8, speed_max:34.2, rot_max:12,  snr_mean:28, course_deviation:12 },
  { mmsi:"538001234", name:"NORDIC CRUDE",        type:"Tanker",          flag:"Marshall Islands", length:310, year_built:2005, gross_tonnage:135000, destination:"Rotterdam",   lat_ais:36.5, lon_ais:15.2, speed_max:17.4, rot_max:8,   snr_mean:32, course_deviation:8 },
  { mmsi:"351004500", name:"PACIFIC STORM",       type:"Tanker",          flag:"Panama",           length:298, year_built:2001, gross_tonnage:118000, destination:"Suez",        lat_ais:12.3, lon_ais:44.8, speed_max:22.1, rot_max:9,   snr_mean:18, course_deviation:65 },
  { mmsi:"636009870", name:"LIBERTAS MARIS",      type:"Tanker",          flag:"Liberia",          length:280, year_built:1998, gross_tonnage:98000,  destination:null,          lat_ais:25.1, lon_ais:57.3, speed_max:15.8, rot_max:7,   snr_mean:22, course_deviation:null },
  { mmsi:"248001122", name:"MALTA SUNRISE",       type:"Tanker",          flag:"Malta",            length:255, year_built:2012, gross_tonnage:82000,  destination:"Dubaï",       lat_ais:24.8, lon_ais:56.1, speed_max:19.3, rot_max:11,  snr_mean:25, course_deviation:22 },
  // Container ships
  { mmsi:"244001500", name:"DELFZIJL EXPRESS",   type:"Container Ship",   flag:"Netherlands",      length:400, year_built:2018, gross_tonnage:200000, destination:"Antwerp",     lat_ais:51.2, lon_ais:2.1,  speed_max:24.8, rot_max:22,  snr_mean:35, course_deviation:5 },
  { mmsi:"211005678", name:"RHEINGOLD ALPHA",     type:"Container Ship",   flag:"Germany",          length:366, year_built:2015, gross_tonnage:178000, destination:"Hambourg",    lat_ais:53.8, lon_ais:8.2,  speed_max:25.3, rot_max:19,  snr_mean:38, course_deviation:7 },
  { mmsi:"563002341", name:"SINGAPORE PRIDE",     type:"Container Ship",   flag:"Singapore",        length:390, year_built:2020, gross_tonnage:210000, destination:"Singapour",   lat_ais:1.2,  lon_ais:103.8,speed_max:26.1, rot_max:21,  snr_mean:40, course_deviation:3 },
  { mmsi:"477001289", name:"HONG KONG TRADER",    type:"Container Ship",   flag:"Hong Kong",        length:350, year_built:2010, gross_tonnage:155000, destination:"Shanghai",    lat_ais:22.5, lon_ais:114.1,speed_max:27.5, rot_max:18,  snr_mean:30, course_deviation:9 },
  { mmsi:"370005600", name:"COLON BRIDGE",        type:"Container Ship",   flag:"Panama",           length:320, year_built:2007, gross_tonnage:132000, destination:"Rotterdam",   lat_ais:48.2, lon_ais:-5.1, speed_max:31.2, rot_max:24,  snr_mean:27, course_deviation:18 },
  // General Cargo
  { mmsi:"228012000", name:"BELLE NORMANDIE",     type:"General Cargo",    flag:"France",           length:185, year_built:2003, gross_tonnage:28000,  destination:"Le Havre",    lat_ais:49.9, lon_ais:0.5,  speed_max:18.5, rot_max:95,  snr_mean:24, course_deviation:11 },
  { mmsi:"232011000", name:"FORTH SPIRIT",        type:"General Cargo",    flag:"UK",               length:162, year_built:2000, gross_tonnage:21000,  destination:"Southampton",  lat_ais:50.3, lon_ais:-1.1, speed_max:15.2, rot_max:28,  snr_mean:31, course_deviation:15 },
  { mmsi:"259006700", name:"OSLO GRAIN",          type:"General Cargo",    flag:"Norway",           length:195, year_built:2009, gross_tonnage:34000,  destination:"Hambourg",    lat_ais:54.2, lon_ais:10.1, speed_max:16.8, rot_max:25,  snr_mean:33, course_deviation:6 },
  { mmsi:"247003400", name:"VENEZIA CARGO",       type:"General Cargo",    flag:"Italy",            length:148, year_built:1997, gross_tonnage:18000,  destination:"Marseille",   lat_ais:38.2, lon_ais:15.5, speed_max:14.1, rot_max:32,  snr_mean:22, course_deviation:28 },
  { mmsi:"273006600", name:"URAL TRADER",         type:"General Cargo",    flag:"Russia",           length:210, year_built:2006, gross_tonnage:42000,  destination:null,          lat_ais:35.8, lon_ais:29.3, speed_max:19.9, rot_max:41,  snr_mean:15, course_deviation:null },
  // Passenger ships
  { mmsi:"228002200", name:"LIBERTÉ DES MERS",    type:"Passenger Ship",   flag:"France",           length:340, year_built:2019, gross_tonnage:180000, destination:"Marseille",   lat_ais:43.2, lon_ais:5.3,  speed_max:27.5, rot_max:16,  snr_mean:42, course_deviation:4 },
  { mmsi:"232004500", name:"BRITTANY QUEEN",      type:"Passenger Ship",   flag:"UK",               length:210, year_built:2014, gross_tonnage:50000,  destination:"Southampton",  lat_ais:50.8, lon_ais:-1.4, speed_max:28.4, rot_max:19,  snr_mean:39, course_deviation:3 },
  { mmsi:"265009900", name:"STOCKHOLM PRINCESS",  type:"Passenger Ship",   flag:"Sweden",           length:280, year_built:2016, gross_tonnage:95000,  destination:"Stockholm",   lat_ais:57.7, lon_ais:11.9, speed_max:26.8, rot_max:15,  snr_mean:41, course_deviation:6 },
  // Fishing vessels
  { mmsi:"227009900", name:"CORSAIRE ROUGE",      type:"Fishing Vessel",   flag:"France",           length:45,  year_built:2001, gross_tonnage:890,    destination:null,          lat_ais:47.5, lon_ais:-3.2, speed_max:12.1, rot_max:28,  snr_mean:20, course_deviation:null },
  { mmsi:"227008800", name:"LA MOUETTE",          type:"Fishing Vessel",   flag:"France",           length:38,  year_built:1998, gross_tonnage:650,    destination:null,          lat_ais:47.8, lon_ais:-4.1, speed_max:10.8, rot_max:35,  snr_mean:17, course_deviation:null },
  { mmsi:"503001122", name:"TASMAN FISHER",       type:"Fishing Vessel",   flag:"Australia",        length:52,  year_built:2010, gross_tonnage:1200,   destination:null,          lat_ais:-34.5,lon_ais:151.3,speed_max:11.5, rot_max:42,  snr_mean:19, course_deviation:null },
  // Military
  { mmsi:"227900001", name:"CAPITAINE NEMO",      type:"Military",         flag:"France",           length:155, year_built:2017, gross_tonnage:7000,   destination:null,          lat_ais:43.5, lon_ais:7.8,  speed_max:30.1, rot_max:48,  snr_mean:5,  course_deviation:null },
  { mmsi:"232900002", name:"HMS DEFENDER",        type:"Military",         flag:"UK",               length:162, year_built:2009, gross_tonnage:8000,   destination:null,          lat_ais:36.1, lon_ais:28.5, speed_max:31.5, rot_max:52,  snr_mean:4,  course_deviation:null },
  // Sailboats
  { mmsi:"227100100", name:"ÉOLE II",             type:"Sailboat",         flag:"France",           length:24,  year_built:2015, gross_tonnage:50,     destination:"Marseille",   lat_ais:43.3, lon_ais:6.1,  speed_max:11.2, rot_max:20,  snr_mean:18, course_deviation:25 },
  // Other / unknowns
  { mmsi:"000000001", name:"UNKNOWN-7749",        type:"Other",            flag:"?",                length:null,year_built:null, gross_tonnage:null,   destination:null,          lat_ais:12.5, lon_ais:44.5, speed_max:16.8, rot_max:33,  snr_mean:12, course_deviation:null },
  { mmsi:"000000002", name:"VESSEL-3312",         type:"Other",            flag:"?",                length:null,year_built:null, gross_tonnage:null,   destination:null,          lat_ais:25.4, lon_ais:57.1, speed_max:22.4, rot_max:44,  snr_mean:10, course_deviation:null },
  // More ships for variety
  { mmsi:"413009900", name:"BEIJING GLORY",       type:"Container Ship",   flag:"China",            length:370, year_built:2019, gross_tonnage:195000, destination:"Singapour",   lat_ais:2.1,  lon_ais:102.5,speed_max:25.8, rot_max:20,  snr_mean:36, course_deviation:8 },
  { mmsi:"338009900", name:"GULF HORIZON",        type:"Tanker",           flag:"USA",              length:290, year_built:2011, gross_tonnage:110000, destination:"Houston",     lat_ais:28.5, lon_ais:-90.2,speed_max:18.2, rot_max:10,  snr_mean:29, course_deviation:14 },
  { mmsi:"351008800", name:"GOLFE DE GASCOGNE",   type:"Container Ship",   flag:"Panama",           length:340, year_built:2004, gross_tonnage:145000, destination:"Rotterdam",   lat_ais:35.2, lon_ais:26.8, speed_max:29.8, rot_max:88,  snr_mean:11, course_deviation:148 },
  { mmsi:"227003344", name:"JEAN BART",           type:"General Cargo",    flag:"France",           length:175, year_built:2002, gross_tonnage:25000,  destination:"Dunkerque",   lat_ais:51.0, lon_ais:2.4,  speed_max:16.1, rot_max:29,  snr_mean:30, course_deviation:18 },
  { mmsi:"566008811", name:"ORIENT STAR",         type:"Container Ship",   flag:"Singapore",        length:355, year_built:2017, gross_tonnage:170000, destination:"Rotterdam",   lat_ais:5.5,  lon_ais:100.3,speed_max:26.3, rot_max:22,  snr_mean:37, course_deviation:6 },
  { mmsi:"247008811", name:"ADRIATICA",           type:"General Cargo",    flag:"Italy",            length:160, year_built:2006, gross_tonnage:20000,  destination:"Gênes",       lat_ais:44.4, lon_ais:8.9,  speed_max:15.5, rot_max:27,  snr_mean:28, course_deviation:9 },
  { mmsi:"255006600", name:"ALGARVE TRADER",      type:"General Cargo",    flag:"Portugal",         length:178, year_built:2004, gross_tonnage:24000,  destination:"Le Havre",    lat_ais:47.2, lon_ais:-3.5, speed_max:17.2, rot_max:31,  snr_mean:26, course_deviation:21 },
  { mmsi:"273009900", name:"MARSHAL ROKOSSOVSKY", type:"General Cargo",    flag:"Russia",           length:220, year_built:1995, gross_tonnage:48000,  destination:null,          lat_ais:33.5, lon_ais:32.8, speed_max:20.5, rot_max:38,  snr_mean:13, course_deviation:null },
  { mmsi:"376001122", name:"HORIZON BLEU",        type:"Container Ship",   flag:"Marshall Islands", length:310, year_built:2013, gross_tonnage:128000, destination:"Hambourg",    lat_ais:50.9, lon_ais:-0.8, speed_max:23.5, rot_max:21,  snr_mean:34, course_deviation:11 },
  { mmsi:"308009900", name:"BAHAMAS EXPRESS",     type:"Passenger Ship",   flag:"Bahamas",          length:296, year_built:2020, gross_tonnage:120000, destination:"Miami",       lat_ais:25.8, lon_ais:-80.1,speed_max:25.1, rot_max:17,  snr_mean:40, course_deviation:5 },
  { mmsi:"416009900", name:"FORMOSA SPIRIT",      type:"Container Ship",   flag:"Taiwan",           length:345, year_built:2014, gross_tonnage:158000, destination:"Busan",       lat_ais:24.1, lon_ais:122.5,speed_max:24.6, rot_max:19,  snr_mean:35, course_deviation:7 },
  { mmsi:"440009900", name:"BUSAN CARRIER",       type:"Container Ship",   flag:"South Korea",      length:360, year_built:2021, gross_tonnage:192000, destination:"Shanghai",    lat_ais:35.1, lon_ais:129.0,speed_max:25.9, rot_max:20,  snr_mean:38, course_deviation:4 },
  { mmsi:"419001122", name:"MUMBAI HORIZON",      type:"Tanker",           flag:"India",            length:270, year_built:2008, gross_tonnage:95000,  destination:"Singapour",   lat_ais:5.2,  lon_ais:100.8,speed_max:16.5, rot_max:9,   snr_mean:24, course_deviation:18 },
  { mmsi:"227005500", name:"THALASSA",            type:"Fishing Vessel",   flag:"France",           length:42,  year_built:2012, gross_tonnage:750,    destination:null,          lat_ais:44.5, lon_ais:-2.2, speed_max:9.8,  rot_max:25,  snr_mean:19, course_deviation:null },
  { mmsi:"227006600", name:"RIVIERA STAR",        type:"Passenger Ship",   flag:"France",           length:230, year_built:2018, gross_tonnage:75000,  destination:"Marseille",   lat_ais:43.1, lon_ais:5.9,  speed_max:24.2, rot_max:14,  snr_mean:40, course_deviation:7 },
  { mmsi:"351009900", name:"DELTA MARIS",         type:"Tanker",           flag:"Panama",           length:265, year_built:2002, gross_tonnage:88000,  destination:"Suez",        lat_ais:37.8, lon_ais:28.4, speed_max:19.8, rot_max:11,  snr_mean:9,  course_deviation:82 },
  { mmsi:"525009900", name:"MALACCA SPIRIT",      type:"Tanker",           flag:"Indonesia",        length:285, year_built:2009, gross_tonnage:105000, destination:"Singapour",   lat_ais:2.8,  lon_ais:101.2,speed_max:17.5, rot_max:8,   snr_mean:23, course_deviation:12 },
  { mmsi:"244009900", name:"AMSTERDAM PRIDE",     type:"Container Ship",   flag:"Netherlands",      length:385, year_built:2022, gross_tonnage:205000, destination:"Rotterdam",   lat_ais:51.9, lon_ais:4.1,  speed_max:25.5, rot_max:20,  snr_mean:42, course_deviation:3 },
  { mmsi:"228099001", name:"HERMÈS",              type:"General Cargo",    flag:"France",           length:155, year_built:2000, gross_tonnage:17000,  destination:"Dunkerque",   lat_ais:51.1, lon_ais:2.8,  speed_max:14.8, rot_max:26,  snr_mean:29, course_deviation:14 },
  { mmsi:"419008800", name:"GUJARAT CARRIER",     type:"Tanker",           flag:"India",            length:260, year_built:2006, gross_tonnage:89000,  destination:null,          lat_ais:22.8, lon_ais:69.5, speed_max:15.2, rot_max:8,   snr_mean:21, course_deviation:null },
  { mmsi:"273001111", name:"VOLGA EXPRESS",       type:"General Cargo",    flag:"Russia",           length:200, year_built:1999, gross_tonnage:38000,  destination:null,          lat_ais:34.9, lon_ais:33.1, speed_max:18.3, rot_max:55,  snr_mean:14, course_deviation:null },
  { mmsi:"538009900", name:"EQUATOR VENTURE",     type:"Tanker",           flag:"Marshall Islands", length:295, year_built:2010, gross_tonnage:112000, destination:"Dubaï",       lat_ais:23.5, lon_ais:58.4, speed_max:20.5, rot_max:10,  snr_mean:20, course_deviation:38 },
  { mmsi:"227007700", name:"BRETAGNE LIBRE",      type:"Fishing Vessel",   flag:"France",           length:35,  year_built:2008, gross_tonnage:480,    destination:null,          lat_ais:48.3, lon_ais:-4.8, speed_max:8.5,  rot_max:20,  snr_mean:18, course_deviation:null },
  { mmsi:"232007700", name:"CELTIC SPIRIT",       type:"General Cargo",    flag:"UK",               length:168, year_built:2003, gross_tonnage:22000,  destination:"Rotterdam",   lat_ais:51.5, lon_ais:1.8,  speed_max:15.9, rot_max:27,  snr_mean:32, course_deviation:12 },
  { mmsi:"211009900", name:"ELBE PIONEER",        type:"Container Ship",   flag:"Germany",          length:330, year_built:2016, gross_tonnage:140000, destination:"Hambourg",    lat_ais:53.4, lon_ais:9.8,  speed_max:24.4, rot_max:18,  snr_mean:37, course_deviation:5 },
  { mmsi:"276001100", name:"SUOMI RANGER",        type:"General Cargo",    flag:"Finland",          length:188, year_built:2011, gross_tonnage:30000,  destination:"Hambourg",    lat_ais:59.4, lon_ais:24.7, speed_max:17.1, rot_max:24,  snr_mean:33, course_deviation:8 },
  { mmsi:"338007700", name:"GULF PATRIOT",        type:"Military",         flag:"USA",              length:170, year_built:2015, gross_tonnage:9500,   destination:null,          lat_ais:26.5, lon_ais:56.2, speed_max:32.8, rot_max:61,  snr_mean:3,  course_deviation:null },
];

// ── Raw detections (pre-computed, filtered by threshold in useDetection) ─────
// confidence = raw score, confidence_final = after zone boost
export const RAW_DETECTIONS = [
  // ARCTIC VOYAGER — Speed Anomaly critique (34 kn pour un tanker)
  { mmsi:"227001000", fraud_type:"Speed Anomaly",       confidence:0.91, confidence_final:0.99, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"Vitesse max 34.2 nd > max 18 nd (Tanker) — zone EXTREME" },
  // PACIFIC STORM — Destination Mismatch
  { mmsi:"351004500", fraud_type:"Destination Mismatch",confidence:0.72, confidence_final:0.87, risk_zone_name:"Bab-el-Mandeb",      risk_zone_level:"ELEVE",   risk_zone_type:"DÉTROIT",    description:"Cap moyen 290° vs cap attendu vers Suez 045° — écart 148°" },
  { mmsi:"351004500", fraud_type:"AIS Disabled",        confidence:0.64, confidence_final:0.74, risk_zone_name:"Bab-el-Mandeb",      risk_zone_level:"ELEVE",   risk_zone_type:"DÉTROIT",    description:"AIS éteint 4h sur les 12 dernières heures dans une zone ELEVE" },
  // BELLE NORMANDIE — Course Anomaly
  { mmsi:"228012000", fraud_type:"Course Anomaly",      confidence:0.82, confidence_final:0.87, risk_zone_name:"Manche",             risk_zone_level:"SURVEILLE",risk_zone_type:"TRAFIC DENSE",description:"ROT max 95°/min > seuil 30°/min pour General Cargo" },
  // COLON BRIDGE — Speed Anomaly
  { mmsi:"370005600", fraud_type:"Speed Anomaly",       confidence:0.76, confidence_final:0.76, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"Vitesse max 31.2 nd > max 26 nd × 1.2 (Container Ship)" },
  // GOLFE DE GASCOGNE — le navire le plus suspect (tous les types)
  { mmsi:"351009900", fraud_type:"Speed Anomaly",       confidence:0.84, confidence_final:0.89, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Vitesse max 29.8 nd > max 26 nd × 1.2 (Container Ship)" },
  { mmsi:"351009900", fraud_type:"Course Anomaly",      confidence:0.88, confidence_final:0.93, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"ROT max 88°/min > seuil 30°/min — manœuvre anormale" },
  { mmsi:"351009900", fraud_type:"Destination Mismatch",confidence:0.91, confidence_final:0.96, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Cap moyen 180° vs Rotterdam attendu 310° — écart 148°" },
  { mmsi:"351009900", fraud_type:"Position Mismatch",   confidence:0.78, confidence_final:0.83, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Écart AIS/radio 380 km — signal suspect, SNR=11 dB" },
  { mmsi:"351009900", fraud_type:"Fake Flag",           confidence:0.69, confidence_final:0.74, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"MID Panama mais émissions radio localisées en Méditerranée" },
  { mmsi:"351009900", fraud_type:"Spoofing",            confidence:0.73, confidence_final:0.78, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Signal AIS répété depuis 2 positions à 12 km d'écart simultanément" },
  { mmsi:"351009900", fraud_type:"Name Change",         confidence:0.65, confidence_final:0.70, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"3 changements de nom enregistrés — ex ORIENT BREEZE, NEPTUNE V" },
  { mmsi:"351009900", fraud_type:"AIS Disabled",        confidence:0.71, confidence_final:0.76, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"AIS coupé 6h dans la zone MODERE, navire obligataire" },
  // CAPITAINE NEMO — AIS Disabled (Military, zone mixte)
  { mmsi:"227900001", fraud_type:"AIS Disabled",        confidence:0.55, confidence_final:0.57, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"AIS coupé 2h — navire militaire, comportement normal" },
  // DELTA MARIS — Position Mismatch + Fake Flag + Destination Mismatch
  { mmsi:"351009900", fraud_type:"Position Mismatch",   confidence:0.78, confidence_final:0.83, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Écart AIS/radio 380 km dans zone MODERE" },
  { mmsi:"351004500", fraud_type:"Position Mismatch",   confidence:0.62, confidence_final:0.72, risk_zone_name:"Bab-el-Mandeb",      risk_zone_level:"ELEVE",   risk_zone_type:"DÉTROIT",    description:"Écart AIS/radio 450 km — SNR très faible 18 dB" },
  // URAL TRADER — Course Anomaly
  { mmsi:"273006600", fraud_type:"Course Anomaly",      confidence:0.58, confidence_final:0.58, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"ROT max 41°/min > seuil 30°/min (General Cargo)" },
  // MARSHAL ROKOSSOVSKY — Course Anomaly + AIS Disabled
  { mmsi:"273009900", fraud_type:"Course Anomaly",      confidence:0.67, confidence_final:0.67, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"ROT max 38°/min > seuil 30°/min" },
  { mmsi:"273009900", fraud_type:"AIS Disabled",        confidence:0.60, confidence_final:0.60, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"Navire de fret obligataire — AIS coupé 3h" },
  // VOLGA EXPRESS — Course Anomaly
  { mmsi:"273001111", fraud_type:"Course Anomaly",      confidence:0.78, confidence_final:0.78, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"ROT max 55°/min > seuil 30°/min — manœuvre evasive suspectée" },
  { mmsi:"273001111", fraud_type:"AIS Disabled",        confidence:0.63, confidence_final:0.63, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"AIS coupé 5h — pavillon russe, zone Méditerranée Est" },
  // UNKNOWN-7749 — dans zone Golfe d'Aden
  { mmsi:"000000001", fraud_type:"AIS Disabled",        confidence:0.73, confidence_final:0.88, risk_zone_name:"Golfe d'Aden",       risk_zone_level:"EXTREME", risk_zone_type:"PIRATERIE",  description:"Navire non identifié dans zone EXTREME piraterie" },
  { mmsi:"000000001", fraud_type:"Fake Flag",           confidence:0.66, confidence_final:0.81, risk_zone_name:"Golfe d'Aden",       risk_zone_level:"EXTREME", risk_zone_type:"PIRATERIE",  description:"MID invalide (000) — pavillon non reconnu" },
  // VESSEL-3312 — dans zone Détroit d'Ormuz
  { mmsi:"000000002", fraud_type:"Speed Anomaly",       confidence:0.67, confidence_final:0.82, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"Vitesse 22.4 nd pour type inconnu, zone EXTREME" },
  { mmsi:"000000002", fraud_type:"AIS Disabled",        confidence:0.60, confidence_final:0.75, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"MID invalide — navire non identifié en zone EXTREME" },
  // VENEZIA CARGO — Destination Mismatch
  { mmsi:"247003400", fraud_type:"Destination Mismatch",confidence:0.56, confidence_final:0.56, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"Cap moyen 270° vs Marseille attendu 280° — écart 28° (tolerable)" },
  // LIBERTAS MARIS — dans zone Hormuz sans destination
  { mmsi:"636009870", fraud_type:"AIS Disabled",        confidence:0.58, confidence_final:0.73, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"Tanker obligataire sans destination déclarée en zone EXTREME" },
  // EQUATOR VENTURE — Destination Mismatch
  { mmsi:"538009900", fraud_type:"Destination Mismatch",confidence:0.61, confidence_final:0.61, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"Cap moyen 220° vs Dubaï attendu 250° — écart 38°" },
  // HMS DEFENDER — dans zone Méditerranée Est
  { mmsi:"232900002", fraud_type:"AIS Disabled",        confidence:0.52, confidence_final:0.57, risk_zone_name:"Méditerranée Orientale",risk_zone_level:"MODERE",risk_zone_type:"SURVEILLANCE",description:"Navire militaire UK — AIS coupé 1h, zone MODERE" },
  // GULF PATRIOT — dans zone Hormuz
  { mmsi:"338007700", fraud_type:"Course Anomaly",      confidence:0.71, confidence_final:0.86, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"ROT max 61°/min pour navire militaire en zone EXTREME" },
  // MALTA SUNRISE — dans zone Hormuz
  { mmsi:"248001122", fraud_type:"Position Mismatch",   confidence:0.59, confidence_final:0.74, risk_zone_name:"Détroit d'Ormuz",    risk_zone_level:"EXTREME", risk_zone_type:"DÉTROIT",    description:"Écart AIS/radio 120 km, tanker zone EXTREME" },
  // NORDIC CRUDE — Spoofing
  { mmsi:"538001234", fraud_type:"Spoofing",            confidence:0.62, confidence_final:0.62, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"Double émission AIS depuis 2 positions simultanées" },
  // ORIENT STAR — dans zone Malacca
  { mmsi:"566008811", fraud_type:"Position Mismatch",   confidence:0.56, confidence_final:0.66, risk_zone_name:"Détroit de Malacca", risk_zone_level:"ELEVE",   risk_zone_type:"PIRATERIE",  description:"Écart AIS/radio 85 km en zone ELEVE" },
  // Name Changes
  { mmsi:"255006600", fraud_type:"Name Change",         confidence:0.71, confidence_final:0.71, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"2 changements de nom — ex ALTAMIRA, BRAGA TRADER" },
  { mmsi:"247008811", fraud_type:"Name Change",         confidence:0.62, confidence_final:0.62, risk_zone_name:null,                 risk_zone_level:null,      risk_zone_type:null,         description:"2 changements de nom — navire construit en 1987, ancienneté" },
  // PACIFIC STORM — Fake Flag dans zone Aden
  { mmsi:"351004500", fraud_type:"Fake Flag",           confidence:0.68, confidence_final:0.78, risk_zone_name:"Bab-el-Mandeb",      risk_zone_level:"ELEVE",   risk_zone_type:"DÉTROIT",    description:"Signal radio localisé loin du pavillon déclaré — anomalie ELEVE" },
];

export const SHIPS = ALL_SHIPS;

// Attach name/type/flag to detections from ships lookup
const shipMap = Object.fromEntries(ALL_SHIPS.map(s => [s.mmsi, s]));
export const DETECTIONS = RAW_DETECTIONS.map(d => ({
  ...d,
  name: shipMap[d.mmsi]?.name  ?? `Ship-${d.mmsi}`,
  type: shipMap[d.mmsi]?.type  ?? "Other",
  flag: shipMap[d.mmsi]?.flag  ?? "?",
}));

export const FRAUD_TYPES_ORDER = [
  "AIS Disabled", "Speed Anomaly", "Course Anomaly", "Position Mismatch",
  "Fake Flag", "Name Change", "Spoofing", "Destination Mismatch",
];

export const SHIP_TYPES_LIST = [
  "Tanker","Container Ship","General Cargo","Passenger Ship",
  "Fishing Vessel","Military","Sailboat","Other",
];

export const DEFAULT_CONFIG = {
  threshold: 0.5,
  speed_max_by_type: {
    "Tanker": 18, "Container Ship": 26, "General Cargo": 20,
    "Passenger Ship": 28, "Fishing Vessel": 14, "Military": 35,
    "Sailboat": 12, "Other": 20,
  },
  default_speed_max: 20,
  overspeed_margin: 1.2,
  rot_max_by_type: {
    "Tanker": 10, "Container Ship": 20, "General Cargo": 20,
    "Passenger Ship": 20, "Fishing Vessel": 25, "Military": 40,
    "Sailboat": 30, "Other": 30,
  },
  default_rot_max: 30,
  rot_threshold_multiplier: 1.5,
  sync_window_hours: 1,
  dist_min_km: 50,
  dist_max_km: 500,
  no_sync_temp_factor: 0.6,
  snr_high: 30,
  snr_mid: 15,
  dest_angle_tolerance: 45,
  boost_by_niveau: { SURVEILLE: 0.02, MODERE: 0.05, ELEVE: 0.10, EXTREME: 0.15 },
};
