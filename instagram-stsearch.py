import sys
import argparse
import math
import time
import datetime
from dateutil import parser
import numpy as np
import urllib2
import json
from sets import Set

reload(sys)
sys.setdefaultencoding("utf-8")

argparser = argparse.ArgumentParser()
argparser.add_argument("ig_access_token", help="instagram access-token", type=str)
argparser.add_argument("lon_min", help="bounding box minimum longitude", type=float)
argparser.add_argument("lon_max", help="bounding box maximum longitude", type=float)
argparser.add_argument("lat_min", help="bounding box minimum latitude", type=float)
argparser.add_argument("lat_max", help="bounding box maximum latitude", type=float)
argparser.add_argument("t_min", help="minimum timestamp", type=str)
argparser.add_argument("t_max", help="maximum timestamp", type=str)
argparser.add_argument("output", help="location of output file", type=str)
argparser.add_argument("-r", help="search radius (default 4900m, using 5000m as specified by the API led to some photos being missed)", type=int, default=4900)
argparser.add_argument("-k", help="show search circles in specified kml file", action="store_true")
argparser.add_argument("-a", help="also retrieve all photos outside of the bbox of users within the result set", action="store_true")
args = argparser.parse_args()	

## static vars
ig_max_time_span = 7
circle_packing = 1.3
##

## slightly adapted from http://www.johndcook.com/blog/2009/04/27/converting-miles-to-degrees-longitude-or-latitude/
earth_radius = 6371.0 # in kms
degrees_to_radians = math.pi/180.0
radians_to_degrees = 180.0/math.pi

def change_in_latitude(kms):
    "Given a distance north, return the change in latitude."
    return (kms/earth_radius)*radians_to_degrees

def change_in_longitude(latitude, kms):
    "Given a latitude and a distance west, return the change in longitude."
    # Find the radius of a circle around the earth at given latitude.
    r = earth_radius*math.cos(latitude*degrees_to_radians)
    return (kms/r)*radians_to_degrees
## end of adaption



t_min = parser.parse(args.t_min)
t_max = parser.parse(args.t_max)
days = (t_max - t_min).days

t_max_list = [t_max - datetime.timedelta(days=x*ig_max_time_span) for x in range(0, (days/ig_max_time_span) + 1)]
t_min_list = [t_max - datetime.timedelta(days=x*ig_max_time_span) for x in range(1, (days/ig_max_time_span) + 2)]
t_min_list = [t_min if x<t_min else x for x in t_min_list]

#print t_max_list
#print t_min_list

lon_list = np.arange(args.lon_min, args.lon_max, change_in_longitude((args.lat_min + args.lat_max)/2, (args.r/1000)*circle_packing))
lat_list = np.arange(args.lat_min, args.lat_max, change_in_latitude((args.r/1000)*circle_packing))

if args.k:
	import simplekml
	from polycircles import polycircles
	kml = simplekml.Kml()
	for lon in lon_list:
		for lat in lat_list:
			polycircle = polycircles.Polycircle(latitude=lat, longitude=lon, radius=args.r, number_of_vertices=36)
			pol = kml.newpolygon(name="", outerboundaryis=polycircle.to_kml())
			pol.style.polystyle.color = simplekml.Color.changealphaint(200, simplekml.Color.green)
	kml.save("instagram-stsearch.kml")

total_calls = len(lon_list)*len(lat_list)*len(t_max_list)
print total_calls, "calls in total without counting recursive calls"

downloaded_photo_ids = Set([])
user_ids = Set([])
call = 1
f = open(args.output, "a")
f.write('id|type|user_id|user_name|link|timestamp|lon|lat|caption|tags\n')
for i in range(0, len(t_max_list)):
	t1 = t_min_list[i]
	t2 = t_max_list[i]
	t1_unix = time.mktime(t1.timetuple())
	t2_unix = time.mktime(t2.timetuple())
	#print t1, t2
	#print t1_unix, t2_unix
	for j in range(0,len(lon_list)):
		lon = lon_list[j]
		for k in range(0,len(lat_list)):
			print 'call', call, '(', round((float(call)/float(total_calls)) * 100, 3), '%)'
			lat = lat_list[k]
			t2_rec = t2_unix
			while True:
				print '  ', t1, t2, lon, lat, time.ctime(float(t2_rec))
				try:
					url = 'https://api.instagram.com/v1/media/search?lat=' + str(lat) + '&lng=' + str(lon) + '&access_token=' + args.ig_access_token + '&distance=' + str(args.r) + '&min_timestamp=' + str(int(t1_unix)) + '&max_timestamp=' + str(int(t2_rec)) + '&count=30'
					print '  ', url
					response = urllib2.urlopen(url, None, 5)
					data = json.load(response)
					print '  ', len(data['data'])
					new_photos = 0
					for photo in range(0, len(data['data'])):
						timestamp = datetime.datetime.fromtimestamp(float(data['data'][photo]['created_time'])).strftime("%Y-%m-%d %H:%M:%S")
						type = data['data'][photo]['type']
						link = data['data'][photo]['link']
						location_lon = data['data'][photo]['location']['longitude']
						location_lat = data['data'][photo]['location']['latitude']
						id = data['data'][photo]['id']
						user_id = data['data'][photo]['user']['id']
						user_name = data['data'][photo]['user']['username']
						caption = data['data'][photo]['caption']
						if caption:
							caption = caption['text'].replace('\n', '')
						else:
							caption = ''
						tags = data['data'][photo]['tags']
						tags = [x.encode('utf-8') for x in tags]
						if not id in downloaded_photo_ids:
							#print '    ', timestamp, '  ', id
							f.write(id + '|' + type + '|' + user_id + '|' + user_name + '|' + link + '|' + timestamp + '|' + str(location_lon) + '|' + str(location_lat) + '|' + caption + '|' + ','.join(tags) + '\n')
							downloaded_photo_ids.add(id)
							user_ids.add(user_id)
							new_photos = new_photos + 1
						else:
							pass
							#print '    ', timestamp, '  ', id, '*'
					if new_photos == 0:
						break
					else:
						t2_rec = int(data['data'][len(data['data'])-1]['created_time']) - 1
					
				except Exception as e:
					print e
					print 'waiting 1 minute...'
					time.sleep(60)
			call = call + 1

if args.a:
	print 'Downloading all photos of users in result set...'
	call = 0
	for user_id in user_ids:
		call = call + 1
		print user_id, '(', call, ' of ', len(user_ids), ', ', round(float(call) / float(len(user_ids)) * 100, 3), '%)'
		next_url = ''
		try:
			url = 'https://api.instagram.com/v1/users/' + user_id + '/media/recent/?access_token=' + args.ig_access_token + '&min_timestamp=' + str(int(time.mktime(t_min.timetuple()))) + '&max_timestamp=' + str(int(time.mktime(t_max.timetuple()))) + '&count=30'
			while True:
				print '  ', url
				response = urllib2.urlopen(url, None, 5)
				data = json.load(response)
				print '  ', len(data['data'])
				for photo in range(0, len(data['data'])):
					# There are basically four scenarios:
					# 1. location = null -> no location so ignore
					# 2. location contains longitude and latitude -> use those values
					# 3. location contains location_id -> fetch longitude and latitude from separate url call; longitude and latitude are not null -> use those values
					# 4. location contains location_id -> fetch longitude and latitude from separate url call; longitude and latitude are null -> no exact location so ignore
					if data['data'][photo]['location'] != None:
						timestamp = datetime.datetime.fromtimestamp(float(data['data'][photo]['created_time'])).strftime("%Y-%m-%d %H:%M:%S")
						type = data['data'][photo]['type']
						link = data['data'][photo]['link']
						if data['data'][photo]['location'].get('longitude'):
							location_lon = data['data'][photo]['location']['longitude']
							location_lat = data['data'][photo]['location']['latitude']
						else:
							response2 = urllib2.urlopen('https://api.instagram.com/v1/locations/' + str(data['data'][photo]['location']['id']) + '?access_token=' + args.ig_access_token, None, 5)
							data2 = json.load(response2)
							if data2['data']['longitude'] != None:
								location_lon = data2['data']['longitude']
								location_lat = data2['data']['latitude']
							else:
								# location through location_id does not contain longitude or latitudes so move on to next photo
								continue
						id = data['data'][photo]['id']
						user_id = data['data'][photo]['user']['id']
						user_name = data['data'][photo]['user']['username']
						caption = data['data'][photo]['caption']
						if caption:
							caption = caption['text'].replace('\n', '')
						else:
							caption = ''
						tags = data['data'][photo]['tags']
						tags = [x.encode('utf-8') for x in tags]
						if not id in downloaded_photo_ids:
							#print '    ', timestamp, '  ', id
							f.write(id + '|' + type + '|' + user_id + '|' + user_name + '|' + link + '|' + timestamp + '|' + str(location_lon) + '|' + str(location_lat) + '|' + caption + '|' + ','.join(tags) + '\n')
						else:
							pass
							#print '    ', timestamp, '  ', id, '*'
			
				if len(data['pagination']) > 0:
					url = data['pagination']['next_url']
				else:
					break
		except Exception as e:
			print e
			print 'waiting 1 minute...'
			time.sleep(60)
f.close()
print "done !"
