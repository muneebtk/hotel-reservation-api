import requests








TOKEN_REFRESH_URL = 'https://d857-103-197-113-37.ngrok-free.app/api/api/token/refresh/'
refresh_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTcyMDk0ODgwMywiaWF0IjoxNzIwNzc2MDAzLCJqdGkiOiJhMjRhNDNkMmU2NTE0ZTg0OGRhMjVlZGFiYjljNWFkMiIsInVzZXJfaWQiOjM1fQ.CphRz_KvrY2ysh-5JOOxDKsYgtRcYC2u-1ofJMkd4MI"

response = requests.post(TOKEN_REFRESH_URL, data={'refresh': refresh_token})
if response.status_code == 200:
    access_token = response.json().get('access')
    print(access_token,"=================")
else:
    print("Failed to refresh token:")
    access_token = None


# endpoint = "https://7f6f-103-246-195-17.ngrok-free.app/api/hotels/search"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }
# data = {
#     "city_name":"Muscat",
#     "hotel_name":"",
#     "checkin_date":"2024-05-20",
#     "checkout_date":"2024-05-30",
#     "members":4,
#     "room":1
# }
# try:
#     get_response = requests.post(endpoint,json=data,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")





    
    
# endpoint = "https://7f6f-103-246-195-17.ngrok-free.app/api/properties/13/room-listing"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }

# data = {
#     'room_id':22,
#     'room_option_id':2,
#     'my_self':True,
#     'first_name':'Visbin',
#     'last_name':'Rojer',
#     'email':'visbinrojer@gmail.com',
#     'contactNumber':'9585110668',
#     'vat':True
# }
# try:
#     get_response = requests.get(endpoint,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")


# access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzIwNzc3ODAzLCJpYXQiOjE3MjA3NzYwMDMsImp0aSI6IjQ0ZGM4ZmEyODhkMTQ0MTk5YTFhMjQ1ZThjYzcyYzI5IiwidXNlcl9pZCI6MzV9.nPKLvXKKM6T7SQIgbCIFi1pxj0noFH_dHaRNV2FJaVY"

session = requests.Session()


# login_endpoint = "https://d857-103-197-113-37.ngrok-free.app/api/v1/auth/login"

# login_data = {
#     "email": "testdevelopment96@gmail.com",
#     "password": "12345"
# }

# try:
#     login_response = requests.post(login_endpoint, json=login_data)

#     print(login_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")


# regitration_data = {
#         "first_name": "Vis",
#         "last_name": "Roj",
#         "email":"zandemo4@gmail.com",
#         "contact_number":"1234567899",
#         "password":"12345",
#         "confirm_password":"12345"
# }


# register_endpoint = "https://d857-103-197-113-37.ngrok-free.app/api/v1/auth/signup"
# register_response = requests.post(register_endpoint, json=regitration_data)

# print(register_response.text)






# category_endpoint = "http://127.0.0.1:5000/api/user/category"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }
# register_response = requests.get(category_endpoint, headers=headers)

# print(register_response.text)




# endpoint = "https://d857-103-197-113-37.ngrok-free.app/api/properties/5/room-listing"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }
# try:
#     get_response = requests.get(endpoint,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")


# endpoint = "http://127.0.0.1:5000/api/HOTEL/search"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }
# data = {
#     "city_name":"kanyakumari",
#     "hotel_name":"",
#     "checkin_date":"2024-06-20",
#     "checkout_date":"2024-06-30",
#     "members":2,
#     "room":1
# }
# try:
#     get_response = session.post(endpoint,json=data,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")



# endpoint = "http://127.0.0.1:5000/api/properties/2/room-listing"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }

# try:
#     get_response = requests.get(endpoint,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")
    
    
# endpoint = "http://127.0.0.1:5000/api/properties/1/book"
# access_token = access_token
# headers={
#     "Authorization": f"Bearer {access_token}"
# }

# data = {
#     'checkin_date': "2024-07-25",
#     'checkout_date': "2024-07-27",
#     'number_of_guests': 2,
#     'number_of_booking_rooms': 2,
#     'room':[1,2],
#     'RoomOptions_id':[2,3],
#     'is_my_self':True,
#     'booking_fname':'Visbin',
#     'booking_lname':'Rojer',
#     'booking_email':'visbinrojer@gmail.com',
#     'booking_mobilenumber':'9585110668',
#     'total_amount': 8500.20
# }
# try:
#     get_response = session.post(endpoint,json=data,headers=headers)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")
    
    
# endpoint = "https://9120-103-197-113-189.ngrok-free.app/api/get-email"
# # access_token = access_token
# # headers={
# #     "Authorization": f"Bearer {access_token}"
# # }
# data = {
#     'email':'visbinrojer@gmail.com'
# }
# try:
#     get_response = session.post(endpoint,json=data)
#     print(get_response.text)
# except Exception as e:
#     print(type(e),"++++++++++++++++")