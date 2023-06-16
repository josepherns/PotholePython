from flask import Flask, render_template, Response
import cv2,torch,time,sys,os,threading,base64,requests,datetime,json,serial
import numpy as np
from flask_socketio import SocketIO, emit
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
from urllib.request import urlopen
from geopy.geocoders import Nominatim
import Jetson.GPIO as GPIO
from ultralytics import YOLO
from ultralytics.yolo.utils.plotting import Annotator
GPIO.setmode(GPIO.BCM)
buzzer=21
GPIO.setup(buzzer,GPIO.OUT)
geolocator = Nominatim(user_agent="geoapiExercises")
#Load Model
model = YOLO('/home/jetson/Desktop/Jetson_Pothole/best.pt')


#Load Serial for SIM808
ser = serial.Serial('/dev/ttyUSB0', baudrate=115200,timeout=1)

ser.write(bytes('AT+CGPSPWR=1\r\n','utf-8')) #turn on the GPS module
ser.readline()
#Initialize variable.
lat='0'
lng='0'
Location='No Location'

'''
Try for GPS, if GPS is activated and receive
coordinates, it will now continue to Detection.
'''
while True:
	try:
		ser.write(bytes('AT+CGNSINF\r\n','utf-8'))
		latlon = ser.readline()
		x = latlon.decode('utf-8')
	except:
		print("trying")
	else:
		print(x)
		if('+CGNSINF:' in x):
			coordinates = x.split(",")
			if(coordinates[3] != '' and coordinates[4] != ''):
				break
			else:
				print("No Gps Yet")
				continue
	finally:
		print("FinallyCode")
	
	time.sleep(1)

# locs() represents the coordinates and location.
def locs():
   global lat, lng, Location
   try:
   	ser.write(bytes('AT+CGNSINF\r\n','utf-8'))
   	latlon = ser.readline()
   	x = latlon.decode('utf-8')
   except:
   	print("Trying")
   else:
   	print("else print here")
   	if('+CGNSINF:' in x):
   		coordinates = x.split(",")
   		if(coordinates[3] != '' and coordinates[4] != ''):
   			lat = coordinates[3]
   			lng = coordinates[4]
   			Location = geolocator.reverse((lat)+","+(lng))
   		else:
   			print("No GPS Signal")
   finally:
   	print("latlnglocation")
locs()
#socket was created for Real time Notification
@socketio.on('connect')
def test_connect():
    print('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

@socketio.on('Notify')
def handle_message(notify):
    print('Notify')
    emit('Notify', notify, broadcast=True)
    
@app.route('/')
def index():
    locs()
    global lat, lng, Location
    return render_template('index.html',lat=lat,lon=lng)
#/location is used to retrieve user location
@app.route('/location')
def location():
    locs()
    global lat, lng, Location
    return json.dumps({'lat':lat,'lon':lng})
    
#video = 'Manila.mp4'
#video = 'Foreign.mp4'
#video = 'LOCB2403.avi'
#video = 'MOVA6662.avi'
#video = 'Qctopasay.mp4'
#camera = cv2.VideoCapture(video)
camera = cv2.VideoCapture(0)


    
def gen():
    global lat, lng, Location
    start = time.time_ns()
    frame_count = 0
    total_frames = 0
    fps = -1
    while True:
        _,frame = camera.read()
        if not _:
            break
        else:
            #frame = cv2.resize(frame, (640,640))
            ret, buffer = cv2.imencode('.jpg', frame)
            results = model(frame,imgsz=512,conf=0.85)
            frame_count += 1
            total_frames += 1
            
            for r in results:
            	annotator = Annotator(frame)
            	
            	boxes = r.boxes
            	for box in boxes:
            		locs()
            		b = box.xyxy[0]
            		c = box.cls
            		annotator.box_label(b,model.names[int(c)])
            		GPIO.output(buzzer,GPIO.HIGH)
            		time.sleep(0.01)
            		GPIO.output(buzzer,GPIO.LOW)
            		dir_path = r'/var/www/html/images'
            		lst = os.listdir(dir_path)
            		URL = 'http://localhost:9191/PostPothole'
            		headers =  {'Content-Type': 'application/json; charset=utf-8'}
            		now = datetime.datetime.now()
            		json_str = json.dumps(now, default=str)
            		res_str = json_str.replace(' ', 'T') 
            		res_str2 = res_str.replace('"', '')   
            		counts = len(lst)
            		yes = str(counts+1)
            		frame = annotator.result()
            		if counts == 1:
            			cv2.imwrite('/var/www/html/images/0.png',frame)
            			converturl = str('0.png')
            			#blobimage = str(my_string,'UTF-8')
            			lat = float(lat)
            			lng = float(lng)
            			Location = str(Location)
            			infos = [res_str2,lat,lng,Location]
            			socketio.emit('Notify',infos)
            			body = {
            			#'blobData' : blobimage,
            			'dateTime' : res_str2,
            			'latitude' : lat,
            			'longitude' : lng,
            			'location' : Location,
            			'imagePath' : converturl
            			}
            			reqs = requests.post(url=URL,headers=headers,json=body)
            		else:
            			cv2.imwrite(f'/var/www/html/images/{yes}.png',frame)
            			converturl = str(f'{yes}.png')
            			#blobimage = str(my_string,'UTF-8')
            			Latitude = float(lat)
            			Longitude = float(lng)
            			Location = str(Location)
            			infos = [res_str2,lat,lng,Location]
            			socketio.emit('Notify',infos)
            			body = {
            			#'blobData' : blobimage,
            			'dateTime' : res_str2,
            			'latitude' : lat,
            			'longitude' : lng,
            			'location' : Location,
            			'imagePath' : converturl
            			}
            			reqs = requests.post(url=URL,headers=headers,json=body)
            if frame_count >= 30:
                end = time.time_ns()
                fps = 1000000000 * frame_count / (end - start)
                frame_count = 0
                start = time.time_ns()
            if fps > 0:
                fps_label = "FPS: %.2f" % fps
                cv2.putText(frame, fps_label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', frame)
            print("Total frames: " + str(total_frames))
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
@app.route('/video_feed')
def video_feed():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')
if __name__ == '__main__':
    #app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
    socketio.run(app,host='0.0.0.0',port=5000,use_reloader=False)
