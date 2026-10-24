
print("Welcome to the quiz")

name = input("What is your name? ")
print("Hello,", name)

questions = [
    ("Capital of Pakistan?", "islamabad"),
    ("Capital of France?", "paris"),
    ("2 + 2?", "4"),
]

score = 0

for question, correct in questions:
    answer = input(question + " ")
    if answer.strip().lower() == correct:
        print("Correct")
        score += 1
    else:
        print("Wrong")

print("You scored", score, "out of", len(questions))

def ask(question, correct):
    answer = input(question + " ")
    if answer.strip().lower() == correct:
        print("Correct")
        return 1
    print("Wrong")
    return 0
 
score = 0
for question, correct in questions:
    score += ask(question, correct)
print("You scored", score, "out of", len(questions))

import requests

 

url = "https://api.open-meteo.com/v1/forecast?latitude=31.52&longitude=74.36&current_weather=true"

response = requests.get(url)

print(response.status_code)

 

data = response.json()

print(data["current_weather"]["temperature"])