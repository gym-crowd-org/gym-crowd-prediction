import requests
from bs4 import BeautifulSoup

url = "https://quotes.toscrape.com"

# Get the HTML of the page
response = requests.get(url)
html = response.text

# Parse the HTML using BeautifulSoup
soup = BeautifulSoup(html, "lxml")

with open("output.html", "w") as f:
    f.write(soup.prettify())
# print(soup.prettify())
