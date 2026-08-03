import csv
import io
import math
from django.core.management.base import BaseCommand
from tracking.models import BusStop, Route, RouteStop

# Complete dataset provided by user
STOPS_CSV = """stop_id,stop_name,stop_lat,stop_lon
12182,Pearl Layout,15.3709381963562,75.1592716475111
9782,Mid Max Cross,15.370549,75.15824
11122,Shabari Nagar,15.368022,75.158745
8442,Hdmc Zonal Office,15.366389,75.157189
9602,Madhura Colony Cross,15.364577,75.157372
7222,Banni Mahakali Temple,15.363071,75.154851
11862,Traffic Police Station,15.362201,75.152709
11062,Sbi Divisional Office,15.361119,75.150033
9302,Keshwapur,15.359334,75.146411
7782,Desai Cross,15.354577,75.141556
7742,Court,15.352469,75.139413
7722,Corporation-H,15.351512,75.141898
10501,Railway Station-H,15.352896,75.145316
7602,Chandrakala Talkies,15.349205,75.14568667
8061,Ganesh Pet,15.34613833,75.14559333
7561,Cbt,15.344364,75.145192
21082,Sulla,15.451011,75.177366
21122,Sulla 2Nd Stop,15.448769,75.178736
21102,Sulla 1St Stop,15.446543,75.178637
21162,Sulla Thota,15.437972,75.179707
21142,Sulla Halla,15.42844,75.180692
17362,Addadari(Keri),15.409786,75.183875
27182,Gudi,15.4024461695607,75.1768713312951
20762,Sai Garden,15.393467,75.169202
21182,Sun City Park,15.38452,75.160372
21422,Gopankoppa Cross/Railway Bridge,15.382372,75.156023
7342,Basaveshwara Park,15.377807,75.155876
8542,Hotel Preeti,15.373659,75.154706
11242,Shanti Nagar,15.368468,75.150124
10702,Ramesh Bhavan,15.364767,75.14885176
18262,Court Circle Sh,15.352338,75.139324
20246,Obs Sh,15.350081,75.135496
27481,Hosur Terminal,15.3569683478474,75.1284487049629
1564,Mahila Vidya Pith (Hosur Terminal),15.357218,75.12918
8582,Hubli Obs (Outside),15.351252,75.13632
20082,Noorani Market,15.3487789070571,75.1380142289294
10123,New English School-H,15.339078,75.1373
7181,Bankapur Chowk,15.33538856,75.14178146
7461,Bidnal Cross Pb Road,15.329689,75.143671
7921,Gabbur,15.31732899,75.14406184
19664,Kundagol Cross,15.29601,75.14664
19621,Kotgunsi,15.291919,75.151483
17421,Adhurgunchi Doddappana Gudi,15.285214,75.153977
17381,Adhurgunchi,15.281908,75.154361
17441,Adhurgunchi Plot,15.2807,75.156848
17401,Adhurgunchi College,15.277585,75.15683
20181,Noolvi Arogya Kendra,15.272147,75.160721
20201,Noolvi Cross,15.271113,75.161774
20901,Sharevada Cross,15.259566,75.169592
20881,Sharevada,15.258353,75.169487
4441,New Boys Hostel,15.433355,74.976928
4683,Pavate Nagar,15.438238,74.986326
6001,Sports Ground,15.440119,74.986766
6602,Working Womens Hostel,15.44398,74.984695
6581,Womens Hostel,15.44507,74.982967
6024,Srinagar,15.447547,74.983128
15502,Parisara Bhavan,15.448028,74.984898
5586,Sarwamangala Hospital,15.449417,74.988477
3382,Jaya Nagar Cross,15.449922,74.990569
5482,Saptapura,15.451606,74.993512
15462,K C D,15.455425,74.998339
3982,Lic,15.456944,75.002966
1045,Jubilee Circle,15.459638,75.008467
1761,Anjuman Circle,15.4603407729333,75.0099570147152
2122,Cbt-D,15.460695,75.011357
19101,Indi Pump Sh,15.336076,75.125706
18822,Grid Sh,15.33163,75.120621
19481,Karwar Road Bypass,15.328872,75.118748
19561,Kempegeri,15.32497,75.114959
17541,Wali,15.32078,75.108272
17501,Anchitageri,15.311444,75.094843
18801,Gopalbhag,15.307121,75.089052
20221,Nursary,15.296297,75.072492
18361,Dhabha,15.294877,75.070682
18381,Dr Banglow,15.289105,75.065764
21381,Water World,15.287434,75.065108
18181,Chalmatti Cross,15.281596,75.058639
19981,Misrikoti Cross,15.275868,75.055297
18481,Chalamatti Factory,15.271365,75.055621
10562,Raj Nagar,15.37146667,75.12814
8362,Gurudev Nagar,15.37043833,75.129625
6782,Adhyapak Nagar,15.371175,75.13626833
9802,Miskin Stop,15.37053333,75.137515
9562,Lion School,15.36931,75.13895667
12062,Vijaya Nagar,15.367623,75.138431
7082,Ashok Nagar,15.365285,75.13667
8102,Ganesh Temple/ Bridge,15.36176,75.137145
10762,Rotary School,15.358331,75.136134
7822,Deshpande Nagar,15.356014,75.138724
7744,Court,15.352378,75.138991
8581,Hubli Obs (Inside),15.350675,75.136422
8221,Glass House,15.352517,75.133526
1583,Hosur Cross,15.354416,75.130512
1563,Mahila Vidya Pith (Hosur Terminal),15.356815,75.129162
8801,Jg Commerce College,15.359031,75.127778
1543,Kims,15.360895,75.126685
8341,Gurudatta Bhavana,15.362619,75.125728
7021,Arts College,15.365018,75.123704
12281,Vidya Nagar (Bvb College),15.367193,75.121493
12621,Prerana College,15.370884,75.118178
11901,Unkal Cross Nh -,15.372411,75.117464
11881,Unkal,15.376703,75.113475
12301,Srinagar Cross H1,15.38187,75.112856
12321,Fci Godown,15.383357,75.108737
1423,Bairidevarakoppa,15.38662,75.105767
7761,Darga,15.389339,75.102112
10901,Sana College,15.390986,75.09877
1383,Apmc,15.393064,75.093861
12341,Amargol Cross,15.3948,75.086272
10001,Navanagar Corridor,15.396536,75.083124
13782,Income Tax,15.398913,75.079406
1344,Rto Office,15.4008906040764,75.0767596000347
13802,K S F C,15.404209,75.070868
1324,Iskcon Temple,15.405163,75.068826
1304,Rayapur,15.405865,75.06677
13882,K M F 1 - D2,15.409168,75.060733
1264,Navalur Railway Station,15.414473,75.055218
1244,Sdm Medical College,15.416924,75.048852
5602,Sattur Cross,15.417729,75.044503
13822,Dental,15.418428,75.041369
13842,Dental Cross,15.4199991055689,75.0392435803566
13862,Navalur Cross,15.42783,75.033251
4341,Navlur,15.428921,75.041477
12562,Ozone,15.430137,75.030563
12542,Navlur K E B,15.431286,75.027258
1184,Lakamanahalli Corridor,15.432456,75.025324
1284,Kmf - D,15.433763,75.023581
6622,Yalakki Shetter Colony,15.43609,75.021633
2602,Gandhi Nagar Cross - D,15.437157,75.019552
12522,Vidya Giri,15.440501,75.017007
12502,Suvarna Petrol Bunk,15.442326,75.015399
12484,Modern Hall,15.444159,75.013418
1124,Toll Naka - D,15.4466541689851,75.0123158859138
1104,Hosa Yallapur Cross,15.4502,75.01085
1084,Nttf,15.451818,75.010468
1064,Court Circle,15.456282,75.006879
2401,Dc Office,15.451831,75.003324
7562,Cbt,15.344365,75.145193
7601,Chandrakala Talkies,15.34935333,75.145615
7941,Gadag Rly Bridge,15.353225,75.147409
11081,Sbi Main Branch,15.355502,75.146554
9301,Keshwapur,15.359123,75.146002
7121,Azad Colony,15.362148,75.14849
10701,Ramesh Bhavan,15.364619,75.14904
11581,Soda Factory,15.368185,75.148082
7363,Bengeri,15.369851,75.145648
11941,Venkatesh Colony,15.371951,75.144337
8301,Gopanakoppa,15.3748,75.144157
10503,Railway Station-H,15.352483,75.144413
7721,Corporation-H,15.351319,75.14188
8523,Hosur Corridor,15.356759,75.12913
9361,Kmc Cross,15.361113,75.126548
11261,Shantinikethana,15.390966,75.098717
1386,Apmc  3Rd Gate,15.393835895632,75.0907922101425
12442,Cancer Hospital Nh,15.3966491643736,75.0831980085984
14921,Nandhi Layout,15.405498,75.078482
14941,Kannayya Apartment,15.402642,75.083281
14961,Judge Quartz Cross,15.402306,75.084465
14982,Police Chouki,15.404876,75.083624
15001,Judge Quartz,15.406897,75.083984
15022,Amargol K H B Colony,15.411347,75.083655
27401,Rpf Office,15.3531407857247,75.1463294938642
10521,Railway Work Shop,15.353085,75.151376
10481,Railway Society,15.352871,75.155741
12101,Vinobha Nagar,15.352801,75.15761
11841,Toll Naka-H,15.352713,75.159751
7581,Chalukya Nagar,15.352599,75.161925
14062,R G S,15.352473,75.164099
27421,Rail Nagar,15.3535984099166,75.1681850801793
10441,Railway Diesel Shed,15.353792,75.168997
9421,Kotari Nagar,15.35479,75.173619
2121,Cbt-D,15.460573,75.011424
1043,Jubilee Circle,15.458668,75.007389
3981,Lic,15.456807,75.002947
3742,Kcd,15.45534,74.998474
15481,Nayadu Girini,15.453372,74.995731
5481,Saptapura,15.451556,74.99356
3381,Jaya Nagar Cross,15.449912,74.990816
5583,Sarwamangala Hospital,15.449312,74.988534
15501,Parisara Bhavan,15.447963,74.985286
6021,Srinagar,15.447315,74.982925
6582,Womens Hostel,15.445182,74.982833
2741,Girls Hostel,15.443829,74.984877
6002,Sports Ground,15.440294,74.986853
4682,Pavate Nagar,15.43824,74.986461
1681,Cbt Hubballi - Hd,15.344522,75.145708
12261,Dr B R Ambedkar Circle 1 - Hd,15.352423,75.145417
1621,Hdmc - Hd,15.350875,75.14088
1601,Hubballi Central Bus Terminal - Hd,15.3506860292075,75.1366910324889
1581,Hosur Cross - Hd,15.354631,75.13043
1561,Hosur Regional Terminal - Hd,15.357106,75.129034
1541,Kims - Hd,15.360084,75.127186
1521,Vidyanagar - Hd,15.363934,75.124931
1501,Bvb College - Hd,15.367526,75.121285
1481,Unakal Cross - Hd,15.370091,75.118911
1461,Unakal - Hd,15.375582,75.114196
1441,Unakal Lake - Hd,15.382314,75.111997
1421,Bairidevarakoppa - Hd,15.386985,75.105499
1401,Shantinikethan - Hd,15.3913313818322,75.0980337915632
1382,Apmc 3Rd Gate - Hd,15.393629,75.092287
1361,Navanagar - Hd,15.397025,75.082709
1341,Rto Office - Hd,15.400535,75.077395
1321,Iskcon Temple - Hd,15.404704,75.070119
1301,Rayapur - Hd,15.406644,75.065151
1281,Kmf 1 - Hd,15.409267,75.060776
28481,Sanjeevini Park-Hd,15.4125207216439,75.0577388015889
1261,Navalur Railway Station - Hd,15.415125,75.053971
1241,Sdm Medical College - Hd,15.417188,75.048409
1221,Sattur - Hd,15.418135,75.042633
1181,Lakamanahalli - Hd,15.432829,75.025028
28504,Yalakki Shettar Cross-Hd,15.4355132366255,75.0221960844809
1161,Gandhi Nagar - Hd,15.437658,75.019256
1141,Vidyagiri - Hd,15.440696,75.016983
1121,Toll Naka - Hd,15.445851,75.012741
1101,Hosa Yallapur Cross - Hd,15.449604,75.01118
1081,Nttf - Hd,15.453491,75.009186
1061,Court Circle - Hd,15.455441,75.007003
1041,Jubilee Circle - Hd,15.457936,75.007389
1021,Dharwad Brts Terminal - Hd,15.46005,75.009442
"""

ROUTES_CSV = """route_id,route_long_name,stop_name
01,Rajeev Nagar ⇆ CBT,"Cbt, Chandrakala Talkies, Railway Station-H, Corporation-H, Hubli Obs (Inside), Glass House, Hosur, Bannigida, Quarters, R.W.H, New Bus Stand-H, 1St Gate, 2Nd Gate, Akshay Park, Ravi Nagar, Ravi Nagar 2Nd Stop, Ravi Nagar 3Rd Stop, Lakshmi Nagar, Lakshmi Nagar Cross, Akshay Colony, Rajeev Nagar Cross, Mruthyunjaya Extension, Rajeev Nagar"
100,Betdur ⇆ Hosur Terminal,"Betdur, Betdur 1St Stop, Betdur Govt School, Water Tank B, Cbm Oil Mill, Basaveshwar Nagar, Sharevada, Sharevada Cross, Noolvi Cross, Noolvi Arogya Kendra, Adhurgunchi College, Adhurgunchi Plot, Adhurgunchi, Adhurgunchi Doddappana Gudi, Kotgunsi, Kundagol Cross, Gabbur Sh, Bidnal Cross Sh, Bankapur Chowk, New English School Sh, Murusavira Matta Cross Sh, Obs Sh, Hosur Terminal, Bankapur Chouk Sh"
1001,New Boys Hostel ⇆ CBT-D,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Jaya Nagar Cross, Sarwamangala Hospital, Parisara Bhavan, Srinagar, Womens Hostel, Girls Hostel, Sports Ground, Pavate Nagar, New Boys Hostel, Working Womens Hostel, K C D, Anjuman Circle"
1002,CBT-D ⇆ Shivagiri,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Vivekananda Circle, Michigan Compound, Galagali Hospital, Bakery Stop, Manjunatha Colony, Shivagiri, Masjid, Jaya Nagar D, Patil Nursery, Naidu Girini, K C D"
1005,DWR SD ⇆ New Bus Stand-D,"Dwr Sd, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D"
1006,CBT-D ⇆ Banashri Nagar,"Cbt-D, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, Gtc, Gtc Cross Sd, Bgs School, Bendre Nagar, Banashri Nagar, Corporation-D"
1008,Yattin Gudda ⇆ CBT-D,"Cbt-D, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, J D Office, Gtc, Pepsi Factory, Dairy, Yattin Gudda Cross, Agri University Gate, Admission Office, Agri College, Yattin Gudda"
1009,Railway Station-D ⇆ Madihal,"Madihal, Siddharama Colony, Joshi Hall, Chidambar Seva Samiti, Murusavira Matta D, Depot Circle, Haveripete, Shivaji Circle, Cbt-D, Jubilee Circle, Court Circle, Head Post Office, Yammikeri, K E Board, Railway Station-D, Rms, Brindhavan, Kalabhawan"
100B-1,Dharwad BRTS Terminal - DH ⇆ Railway Station - DH,"Dharwad Brts Terminal - Dh, Jubilee Circle - Dh, Court Circle - Dh, Nttf - Dh, Toll Naka - Dh, Gandhi Nagar - Dh, Sdm Medical College - Dh, Navanagar - Dh, Kims - Dh, Hosur Regional Terminal - Dh, Hosur Cross - Dh, Hubballi Central Bus Terminal - Dh, Hdmc - Dh, Dr B R Ambedkar Circle - Dh, Railway Station - Dh"
100B-2,Railway Station - HD ⇆ Dharwad BRTS Terminal - HD,"Railway Station - Hd, Dr B R Ambedkar Circle 1 - Hd, Hdmc - Hd, Hubballi Central Bus Terminal - Hd, Hosur Cross - Hd, Hosur Regional Terminal - Hd, Kims - Hd, Navanagar - Hd, Sdm Medical College - Hd, Gandhi Nagar - Hd, Toll Naka - Hd, Nttf - Hd, Court Circle - Hd, Jubilee Circle - Hd, Dharwad Brts Terminal - Hd"
101,Hosur Terminal ⇆ Bommasamudra,"Bommasamudra, Bommasamudra 1St Stop, Bommasamudra Cross, Belgali, Belgali Govt School, Monkey Factory, Noolvi Cross, Noolvi, Adhurgunchi, Budurshingi, Kundagol Cross, Gabbur Sh, Bidnal Cross Sh, Bankapur Chouk Sh, New English School Sh, Murusavira Matta Cross Sh, Obs Sh, Hosur Terminal"
1010,Railway Station-D ⇆ Taj Nagar D,"Taj Nagar D, Hashmi Nagar, Malapura, Goudar Oni, Masjid, Ramana Gouda Cross, Shivaji Circle, Cbt-D, Court Circle, Yammikeri, Railway Station-D, Ganapathi Gudi"
1012,Taj Nagar D ⇆ CBT-D,"Cbt-D, Shivaji Circle, Ganapathi Gudi, Ramana Gouda Cross, Masjid, Goudar Oni, Malapura, Hashmi Nagar, Taj Nagar D"
1013-1,CBT-D ⇆ Nehru Nagar,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Jaya Nagar Cross, Sarwamangala Hospital, Parisara Bhavan, Srinagar Cross, Shivalaya, Ics College, Nehru Nagar Cross, Neharu Nagar 1St Stop, Nehru Nagar"
1013-2,Neharu Nagar ⇆ CBT-D,"Neharu Nagar, Neharu Nagar 1St Stop, Nehru Nagar Cross, Ics College, Shivalaya, Srinagar, Parisara Bhavan, Sarwamangala Hospital, Jaya Nagar Cross, Saptapura, K C D, Lic, Jubilee Circle, Anjuman Circle, Cbt-D"
1014,CBT-D ⇆ Pavate Nagar,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Jaya Nagar Cross, Sarwamangala Hospital, Parisara Bhavan, Srinagar, Womens Hostel, Girls Hostel, Pavate Nagar, Working Womens Hostel, K C D, Anjuman Circle"
1015,CBT-D ⇆ Radhakrishna Nagar,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Michigan Compound, Galagali Hospital, Sarwamangala Hospital, Parisara Bhavan, Srinagar Cross, Shivalaya, Radhakrishna Nagar, Srinagar, Naidu Girini, K C D"
1016,Sai Nagar-D ⇆ CBT-D,"Cbt-D, Jubilee Circle, Lic, Kcd, Nayadu Girini, Saptapura, Saptapura School, Shripadha Nagar, Sai Nagar 1St Stop, Sai Nagar-D, Shripada Nagar Cross, K C D"
1017,CBT-D ⇆ Kalyan Nagar,"Cbt-D, Jubilee Circle, Court Circle, Brindhavan, Head Post Office, Dc Office, Uday Hostel, Old Central School, Kariyyamma Temple, Barakotri, Barakotari Bridge, Navodhaya Nagar, Pavate Nagar, Bhala Balaga, Nisarga, Hanumanthaa Nagar Cross, Twok Quartz, 9Th Cross Kalyan Nagar, Kalyan Nagar, C B Nagar, Headpost Office"
1018,CBT-D ⇆ Anjana Nagar-D1,"Cbt-D, Jubilee Circle, Lic, Kcd, Dasanakoppa, Canara Colony, Banashankeri Nagar, Sai Nagar-D, Vinayaka Nagar Cross, Vinayaka Nagar D, Paper Mill, Kelgeri, Anjaneya School Stop, Kelageri Anjaneya 1St Stop, Anjana Nagar-D1, K C D"
1019,Sangolli Rayana Nagar ⇆ CBT-D,"Cbt-D, Jubilee Circle, Court Circle, Nttf, Hosa Yallapur Cross, Toll Naka - D, Modern Hall, Rajathagiri, Saraswathipura, Tejasvi Nagar Bridge, Tajesavi Nagar, Tejasvi Nagar Bus Stop, Sangolli Rayanna Nagar 1St Cross, Sangolli Rayana Nagar, Vijaya Bank-D"
102,Gokul ⇆ RLY 3RD Gate,"Gokul, Anjaneya Nagar, Gokul Cross, K L E College, Airport, B D K, Kec, Arjun Vihar Cross, Neharu Nagar Water Tank, Silver Town Cross, Manjunatha Nagar Cross, Basaveshwara Nagar Cross, Akshay Park, 2Nd Gate, 1St Gate, New Bus Stand-H, Rwh, Quarters, Bannigida, Hosur, Hubli Obs (Outside), Corporation-H, Railway Station-H, Rly 3Rd Gate, Hubli Obs (Inside)"
1020,Chaithanya Nagar ⇆ CBT-D,"Cbt-D, Jubilee Circle, Lic, K C D, Dasanakoppa Cross, Canara Colony, Kusuma Nagar, Banashankeri Nagar, Sai Nagar-D, Vinayaka Nagar Cross, Chaithanya Nagar Cross, Std Booth, Chaithanya Nagar"
1021,Vinayaka Nagar D ⇆ CBT-D,"Cbt-D, Jubilee Circle, Lic, K C D, Dasanakoppa Cross, Canara Colony, Kusuma Nagar, Banashankeri Nagar, Sai Nagar-D, Vinayaka Nagar Cross, Chaithanya Nagar Cross, Vinayaka Nagar D"
1024,CBT-D ⇆ Sampige Nagar,"Cbt-D, Jubilee Circle, Lic, K C D, Dasanakoppa Cross, Lic Quarters, Narayanapura, German Hospital, Jambagi Hospital, Bendre Bhavana, Sadhankeri, St Antony Circle, Vikas Nagar, Bgs School, Bendre Nagar, Sampige Nagar 1St Stop, Sampige Nagar 2Nd Stop, Basavareddy College, Sampige Nagar Cross, Sampige Nagar, Sampige Nagar 3Rd Stop"
1025-1,CBT-D ⇆ Railway Station-D,"Cbt-D, Jubilee Circle, Court Circle, Taluk Panchayat, Head Post Office, Yammikeri, Rama Mandira, Rms, Railway Station-D"
1025-2,Railway Station-D4 ⇆ CBT-D,"Railway Station-D4, Rms, K E Board, Yammikeri, Head Post Office, Taluk Panchayat, Court Circle, Jubilee Circle, Cbt-D"
1026,Bendre Nagar ⇆ Railway Station-D,"Railway Station-D, Rms, K E Board, Yammikeri, Head Post Office, Brindhavan, Court Circle, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, Gtc, Gtc Cross Sd, Bgs School, Bendre Nagar, Corporation-D, Taluk Panchayat, Rama Mandira"
1027,Agri College ⇆ CBT-D,"Cbt-D, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, J D Office, Gtc, Pepsi Factory, Dairy, Yattin Gudda Cross, Agri University Gate, Admission Office, Agri College"
1028-1,CBT-D ⇆ Shiridi Nagar D1,"Cbt-D, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, J D Office, Gtc, Pepsi Factory, Dairy, Yattin Gudda Cross, Agri University Gate, Airtech, Basava Colony, Basava Nagar Colony 2Nd Stop, Gurukrupa Nagar, Shiridi Nagar Cross, Shiridi Nagar D1"
1028-2,Shiridi Nagar D2 ⇆ CBT-D,"Shiridi Nagar D2, Shiridi Nagar Cross, Gurukrupa Nagar, Basava Nagar Colony 2Nd Stop, Basava Colony, Airtech, Agri University Gate, Yattin Gudda Cross, Dairy, Pepsi Factory, Gtc, J D Office, Kvg Bank, New Bus Stand-D, New Sp Office, Mental Hospital, K C Park, Old Sp Office, Corporation-D, Cbt-D"
1029,Railway Station-D ⇆ Dharwad High Court,"Railway Station-D, Rms, K E Board, Yammikeri, Head Post Office, Brindhavan, Court Circle, Jubilee Circle, Old Sp Office, K C Park, Mental Hospital, New Sp Office, New Bus Stand-D, Kvg Bank, J D Office, Gtc, Pepsi Factory, Dairy, Yattin Gudda Cross, Agri University Gate, Airtech, Narendra Cross, K E B (Power Grid), Mummigatti 1St Cross, Mummigatti, Garag Cross, Tata Motors Gate, High Court Gate, Dharwad High Court, Rama Mandira"
103,Hosur Terminal ⇆ Byahatti,"Hosur Terminal, Obs Sh, Court Circle Sh, Keshwapur Sh, Madhura Colony Sh, Shabiri Nagar Cross Sh, Srinivas Garden, Oxford College, Durga Colony / Neeli Bangle, Ram Honda, Kusgal Siddharuda Matta, Kusgal Maruthi Nagar, Ms, Kusgal, Kusgal Plot, Furniture Factory, Halla, M/S L1, Byahatti 1St Stop, Byahatti 2Nd Stop, Byahatti, M/S L"
1030,New Bus Stand-D ⇆ Railway Station-D,"New Bus Stand-D, New Sp Office, Mental Hospital, K C Park, Old Sp Office, Jubilee Circle, Court Circle, Taluk Panchayat, Head Post Office, Yammikeri, Rama Mandira, Rms, Railway Station-D, K E Board, Brindhavan"
200A-1,CBT Hubballi - HD ⇆ Dharwad BRTS Terminal - HD,"Cbt Hubballi - Hd, Dr B R Ambedkar Circle 1 - Hd, Hdmc - Hd, Hubballi Central Bus Terminal - Hd, Hosur Cross - Hd, Hosur Regional Terminal - Hd, Kims - Hd, Vidyanagar - Hd, Bvb College - Hd, Unakal Cross - Hd, Unakal - Hd, Unakal Lake - Hd, Bairidevarakoppa - Hd, Shantinikethan - Hd, Apmc 3Rd Gate - Hd, Navanagar - Hd, Rto Office - Hd, Iskcon Temple - Hd, Rayapur - Hd, Kmf 1 - Hd, Sanjeevini Park-Hd, Navalur Railway Station - Hd, Sdm Medical College - Hd, Sattur - Hd, Lakamanahalli - Hd, Yalakki Shettar Cross-Hd, Gandhi Nagar - Hd, Vidyagiri - Hd, Toll Naka - Hd, Hosa Yallapur Cross - Hd, Nttf - Hd, Court Circle - Hd, Jubilee Circle - Hd, Dharwad Brts Terminal - Hd"
200A-2,Dharwad BRTS Terminal - DH ⇆ CBT Hubballi - DH,"Dharwad Brts Terminal - Dh, Jubilee Circle - Dh, Court Circle - Dh, Nttf - Dh, Hosa Yallapur Cross - Dh, Toll Naka - Dh, Vidyagiri - Dh, Gandhi Nagar - Dh, Yalakki Shettar Cross-Dh, Lakamanahalli - Dh, Sattur - Dh, Sdm Medical College - Dh, Navalur Railway Station - Dh, Sanjeevini Park-Dh, Kmf 1 - Dh, Rayapur - Dh, Iskcon Temple - Dh, Rto Office - Dh, Navanagar - Dh, Apmc 3Rd Gate - Dh, Shantinikethan - Dh, Bairidevarakoppa - Dh, Unakal Lake - Dh, Unakal - Dh, Unakal Cross - Dh, Bvb College - Dh, Vidyanagar - Dh, Kims - Dh, Hosur Regional Terminal - Dh, Hosur Cross - Dh, Hubballi Central Bus Terminal - Dh, Hdmc - Dh, Dr B R Ambedkar Circle - Dh, Cbt Hubballi - Dh"
"""

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class Command(BaseCommand):
    help = 'Imports real NWKRTC bus stops and routes dataset into Travel Dost.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('=== NWKRTC / BRTS Data Importer ==='))
        
        # 1. Import Bus Stops
        stops_by_name = {}
        stop_count = 0
        reader = csv.DictReader(io.StringIO(STOPS_CSV.strip()))
        for row in reader:
            sname = row['stop_name'].strip()
            lat = float(row['stop_lat'])
            lon = float(row['stop_lon'])
            stop_id = row['stop_id'].strip()

            bus_stop, created = BusStop.objects.get_or_create(
                stop_name=sname[:150],
                defaults={
                    'area': 'Hubballi-Dharwad Region',
                    'latitude': lat,
                    'longitude': lon,
                    'description': f"NWKRTC Stop ID #{stop_id}"
                }
            )
            if not created:
                bus_stop.latitude = lat
                bus_stop.longitude = lon
                bus_stop.save()

            stops_by_name[sname.lower()] = bus_stop
            stop_count += 1

        self.stdout.write(self.style.SUCCESS(f'Imported/Updated {stop_count} Bus Stops.'))

        # 2. Import Bus Routes and RouteStops
        route_reader = csv.DictReader(io.StringIO(ROUTES_CSV.strip()))
        routes_imported = 0
        stops_linked = 0

        for row in route_reader:
            route_id = row['route_id'].strip()
            long_name = row['route_long_name'].strip()
            raw_stops = [s.strip() for s in row['stop_name'].split(',') if s.strip()]

            if not raw_stops:
                continue

            r_name = f"Route {route_id}: {long_name}"[:150]
            start_stop = raw_stops[0][:150]
            end_stop = raw_stops[-1][:150]

            route_obj, _ = Route.objects.get_or_create(
                route_name=r_name,
                defaults={
                    'start_point': start_stop,
                    'end_point': end_stop,
                    'description': f"NWKRTC Route {route_id} ({long_name})"
                }
            )

            # Clear existing route stops to avoid duplicate sequence errors
            RouteStop.objects.filter(route=route_obj).delete()

            cumulative_dist = 0.0
            prev_stop = None

            for idx, sname in enumerate(raw_stops, 1):
                # Search for bus stop object
                stop_obj = stops_by_name.get(sname.lower())
                if not stop_obj:
                    # Create on the fly if missing from stops table
                    stop_obj, _ = BusStop.objects.get_or_create(
                        stop_name=sname[:150],
                        defaults={
                            'area': 'Hubballi-Dharwad Region',
                            'latitude': 15.3647,
                            'longitude': 75.1240,
                            'description': 'NWKRTC Bus Stop'
                        }
                    )
                    stops_by_name[sname.lower()] = stop_obj

                if prev_stop:
                    dist = haversine_km(
                        prev_stop.latitude, prev_stop.longitude,
                        stop_obj.latitude, stop_obj.longitude
                    )
                    cumulative_dist += dist

                RouteStop.objects.create(
                    route=route_obj,
                    bus_stop=stop_obj,
                    stop_order=idx,
                    distance_from_start_km=round(cumulative_dist, 2)
                )
                prev_stop = stop_obj
                stops_linked += 1

            routes_imported += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {routes_imported} Bus Routes with {stops_linked} RouteStop linkages!'))
