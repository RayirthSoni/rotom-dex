import bs4
import requests
import os

# get path of current directory
CURRENT_WORKING_DIRECTORY = os.getcwd()

# url from where data is being fetched
POKEMON_DB_WEBSITE = 'https://pokemondb.net/'

# pokemon for which need information
pokemon_name = input('Enter Pokemon about which you wish to know : ')

# remove leading and traling spaces
pokemon_name = pokemon_name.strip()

# fetch html content from the url
def get_html_content(pokemon_website_url):
    html_content = requests.get(pokemon_website_url)
    soup = bs4.BeautifulSoup(html_content.text, 'lxml')
    
    
def search_pokemon(pokemon_website_url, pokemon_name):
    pokemon_website = os.path.join(pokemon_website_url, 'pokedex', pokemon_name)
    print(pokemon_website)
    
def get_pokemon_information(pokemon_name):
    pass
    
    

get_html_content(POKEMON_DB_WEBSITE)
search_pokemon(POKEMON_DB_WEBSITE, pokemon_name)
get_pokemon_information(pokemon_name)