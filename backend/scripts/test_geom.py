import json
import math

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 
    return c * r

def standardize_lng(lng):
    # keep inside -180 to 180
    while lng > 180:
        lng -= 360
    while lng < -180:
        lng += 360
    return lng

def test():
    # simulate searoute output across dateline
    segs = [[178, 0], [179, 0], [181, 0], [182, 0]]
    
    multi_line = []
    current_line = []
    
    for pt in segs:
        lat = pt[1]
        lng = standardize_lng(pt[0])
        
        if len(current_line) > 0:
            prev_lat, prev_lng = current_line[-1]
            if abs(lng - prev_lng) > 180: # e.g. 179 to -179
                multi_line.append(current_line)
                current_line = []
        
        current_line.append([lat, lng])
        
    if current_line:
        multi_line.append(current_line)
        
    print(multi_line)

test()
