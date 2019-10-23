import json
import subprocess
import time
from datetime import datetime, timedelta
import gphoto2 as gp
import signal, os, subprocess
import random
from PIL import Image, ImageDraw, ImageFont
from twilio.rest import Client
import ibm_boto3
from ibm_botocore.client import Config, ClientError

#enter IBM Cloud Credentials

COS_ENDPOINT = "COS_API"
COS_API_KEY_ID = "COS_API_KEY_ID"
COS_AUTH_ENDPOINT = "IDENTITY_TOKEN"
COS_RESOURCE_CRN = "RESOURCE_TOKEN"


# create IBM CLOUD resource

cos = ibm_boto3.resource("s3",
                         ibm_api_key_id =COS_API_KEY_ID,
                         ibm_service_instance_id=COS_RESOURCE_CRN,
                         ibm_auth_endpoint=COS_AUTH_ENDPOINT,
                         config=Config(signature_version="oauth"),
                         endpoint_url=COS_ENDPOINT
)

# Function that resizes/compresses the Image before Upload to IBM Cloud Storage

def resize(input_file):
    
    image_Path_Input = '/home/pi/Desktop/CUNYhackathon/Images/'
    image_Path_Output = '/home/pi/Desktop/CUNYhackathon/Output/'

    

    im = Image.open(image_Path_Input + input_file)
    im_width, im_height = im.size

    print('im.size', im.size)
    im = im.resize((int(im_width/4), int(im_height/4)), Image.ANTIALIAS)

   

    im.save(image_Path_Output + input_file)


# Function which sends a text to relevant parties which utilizes Twilio's API

def send_message(message_body):
  
    # Enter twilio API Credentials below  
    account_sid = "Enter twilio Account Id Here"
    auth_token = "Enter twilio API Auth Token Here"

    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body = message_body,
        from_ = "ENTER YOUR TWILIO NUMBER HERE",
        to = "ENTER NUMBERS YOU WANT TO SEND THE TEXT ALERTS TO HERE"
    )

    print(message.sid)
    
    
# Function which uploads data onto the IBM Cloud Storage

def multi_part_upload(bucket_name, item_name, file_path):
    try:
        print("Starting file transfer for {0} to bucket: {1}\n".format(item_name, bucket_name))
        part_size = 1024 * 1024 * 5
        
        file_threshold = 1024 * 1024 * 15
        
        transfer_config = ibm_boto3.s3.transfer.TransferConfig(
            multipart_threshold = file_threshold,
            multipart_chunksize = part_size
        )
        
        with open(file_path, "rb") as file_data:
            cos.Object(bucket_name, item_name).upload_fileobj(
                Fileobj=file_data,
                Config=transfer_config
            )
            
        print("Transfer for {0} Complete!\n".format(item_name))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to complete multi-part upload: {0}".format(e))


# Function which takes in end_time (akin to a Timer) as a parameter and keeps on taking Images from the camera (approx. every 6 seconds), which is connected to Raspberry Pi  
# Utilizes gphoto2 library
# Also Classifies the Images based on our custom IBM Watson AI model to detect Wildfires & Deforestation and sends a text message based on classification result

def captureImages(end_time):
      
    while datetime.now() < end_time:
        picName = datetime.now().strftime("%H:%M:%S") + str(random.randint(1,999)) + ".jpg" #added a random int ranging b/w 1 to 999 in Img name as string to avoid over-writing of data
        os.system("gphoto2 --capture-image-and-download --filename Images/" + picName)
        resize(picName)
        # Requesting IBM Watson API to attain results from the custom model
        returned_output = subprocess.check_output(['curl', '-s', '-X', 'POST', '-u', "apikey:ENTER CUSTOM WATSON AI MODEL API KEY HERE", '-F', "images_file=@Output/"+picName, '-F', "threshold=0.6", '-F', "classifier_ids=ENTER IBM WATSON AI MODEL's CLASSIFIER ID HERE", "ENTER MODEL's URL HERE"])

        json_data = json.loads(returned_output) # parsing output from IBM Watson API as JSON
        
        classify = "unclassified" # Added a negative classifier to avoid bias in the result
        if len(json_data["images"][0]["classifiers"][0]["classes"] > 0 :  
          classify = json_data["images"][0]["classifiers"][0]["classes"][0]["class"]
          # send message using Twilio based on IBM Watson AI Model's Classification of the uploaded Img
          if classify == "fire":
              #send message with body fire
              send_message("There is a fire !!!")
              print("fire")
          elif classify == "deforest":
              #send message with body deforest
              send_message("The forest is gone :( :( :(")
              print("deforest")
        
        # add text to image
        img = Image.open("Output/"+picName)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("CaviarDreams.ttf", 48)
        draw.text((0, 0),classify,(255,255,255),font=font)
        img.save("Output/"+picName)

        
        # Uploading picture on the IBM Cloud from Local Directory of Raspberry Pi
        multi_part_upload('hackathon2019', picName, '/home/pi/Desktop/CUNYhackathon/Images/'+picName)
        time.sleep(2)
        os.system("rm Images/*") # Deleting pictures from local directory to avoid running out of space on Raspberry Pi
        os.system("rm Output/*") # Deleting compressed pictures from local directory to avoid running out of space on Raspberry Pi
        time.sleep(1)

captureImages(datetime.now() + timedelta(seconds = 120)) # Time Delta acts as a timer. Pi Keeps on taking pics for 120 seconds in this case.

