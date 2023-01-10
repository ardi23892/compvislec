import streamlit as st
import cv2
import os
import numpy as np
import pandas as pd
import pymysql
import zipfile
from datetime import datetime

#DB Connection
connection = pymysql.connect(host='localhost', user='root', passwd='', database='cv_attendance')
cursor = connection.cursor()

face_recog = cv2.face.LBPHFaceRecognizer_create()
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

def train():
    path = 'dataset'
    images = []
    faces = []
    names = os.listdir(path)
    class_id = []
    train_class = []

    for idx, name in enumerate(names):
        dir_path = path+'/'+name

        for img_name in os.listdir(dir_path):
            img_path = dir_path+'/'+img_name
            img = cv2.imread(img_path)

            if img is None:
                continue

            images.append(img)
            class_id.append(idx)

    for idx, train_img in enumerate(images):
        train_img = cv2.cvtColor(train_img, cv2.COLOR_BGR2GRAY)
        detected_face = face_cascade.detectMultiScale(
            train_img, 
            scaleFactor=1.05, 
            minNeighbors=6
            )

        if len(detected_face)<1:
            continue
        
        for face_rect in detected_face:
            x,y,h,w = face_rect
            face_img = train_img[y:y+h, x:x+w]
            faces.append(face_img)
            if class_id is not None:
                train_class.append(class_id[idx])
    
    face_recog.train(faces, np.array(train_class))

    return face_recog
    
def attendance():
    st.title('Face Recognizing Attendance System')

    img_file_buffer = st.camera_input("Take a picture")

    if img_file_buffer is not None:
        face_recog = train()
        
        # To read image file buffer with OpenCV:
        bytes_data = img_file_buffer.getvalue()
        input = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)

        image_gray = cv2.cvtColor(input, cv2.COLOR_BGR2GRAY)

        detected_face = face_cascade.detectMultiScale(image_gray, scaleFactor=1.05, minNeighbors=6)

        if len(detected_face)<1:
            return st.error('No face detected, please retake the picture!')
        elif len(detected_face)>1:
            return st.error('Multiple face detected, please take picture one at a time!')

        x,y,h,w = detected_face[0]
        face_img = image_gray[y:y+h, x:x+w]

        res, confidence = face_recog.predict(face_img)
        record = res+1
        cursor.execute(f"SELECT * FROM record WHERE id = '{record}'")
        data = cursor.fetchone()

        cv2.rectangle(input, (x,y), (x+w, y+h), (255,0,0), 1)
        text = data[1]+': '+str(confidence)
        cv2.putText(input, text, (x,y-10), cv2.FONT_HERSHEY_PLAIN, 1.5, (0,255,0), 2)

        st.image(cv2.cvtColor(input, cv2.COLOR_BGR2RGB))

        st.subheader('Identity Confirmation')
        st.markdown('Name       : '+data[1])
        st.markdown('Gender     : '+data[4])
        st.markdown('Company ID : '+data[2])
        st.markdown('Role       : '+data[3])

        st.info('If the above data is not yours, please retake the picture!')

        if st.button('Confirm'):
            with st.spinner():
                now = datetime.now()
                date = datetime.today()
                time = now.strftime("%H:%M:%S")
                if date.hour > 9:
                    late = 'Y'
                else:
                    late = 'N'

                attend = f"INSERT INTO attendance(record_id,date, time, late) VALUES('{data[0]}', '{date}', '{time}', '{late}')"
                cursor.execute(attend)
                connection.commit()
                st.success("Attendance recorded!")


def register():
    st.title('New Record Register')
    st.markdown("**Please fill the below form :**")

    with st.form(key="Form :", clear_on_submit=True):
        Name = st.text_input("Name : ")
        Gender = st.selectbox("Gender : ",
        ('Male', 'Female'))
        Id = st.text_input('Company ID : ')
        Role = st.selectbox('Company Role : ',
        ('Intern', 'Employee', 'Executives','Developer'))
        File = st.file_uploader(label = "Compressed pictures file : ", type=["zip"])
        st.info('Please compress your face images into zip file! (with minimum of 5 images)')
        Submit = st.form_submit_button(label='Submit')

    if Submit:
        insert = f"INSERT INTO record(name, company_id, role, gender) VALUES('{Name}', '{Id}', '{Role}', '{Gender}')"
        cursor.execute(insert)
        connection.commit()

        cursor.execute("SELECT MAX(id) FROM record")

        id=cursor.fetchone()
        
        path = os.path.join("dataset", str(id[0]))
        os.mkdir(path)

        with zipfile.ZipFile(File, 'r') as zip_ref:
            zip_ref.extractall(path)

        train()

        st.success("New record registered!")

def info():
    st.title('Check Attendance Data')

    date = st.date_input('Select Date :')

    if st.button('Search'):
        cursor.execute(f"SELECT record.name, attendance.date, attendance.time, attendance.late FROM attendance INNER JOIN record ON attendance.record_id=record.id WHERE attendance.date='{date}'")
        row_count = cursor.rowcount
        
        if row_count>0:
            rows = cursor.fetchall()
    
            df = pd.DataFrame(rows, columns=['Name', 'Date', 'Time', 'Late'])

            df['Time'] = df['Time'].values.astype('datetime64[ns]')
            df['Time']=df['Time'].dt.strftime('%H:%M:%S')

            st.dataframe(df)
        else:
            st.subheader(f'No attendance record found at {date}')


#WEBAPP
st.sidebar.header('Page Menu')
page = st.sidebar.selectbox('Select page',('Attendance  ⏱️','Register New Data   💾', 'Attendance Information    📊'))

if page == 'Attendance  ⏱️':
    attendance()
elif page == 'Register New Data   💾':
    register()
else:
    info()