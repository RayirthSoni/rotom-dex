import bs4
import requests
import os

# get path of current directory
CURRENT_WORKING_DIRECTORY = os.getcwd()

# url from where data is being fetched
POKEMON_DB_WEBSITE = 'https://pokemondb.net/'

# url for national pokedex where names and types of pokemons are present
NATIONAL_POKEDEX_WEBSITE = 'https://pokemondb.net/pokedex/national'

# fetch html content from the url
def get_html_content(pokemon_website):
    
    html_content = requests.get(pokemon_website)
    soup = bs4.BeautifulSoup(html_content.text, 'lxml')
    
    return soup


def search_pokemon(base_url, pokemon_name):

    try:
        pokemon_website = os.path.join(base_url, 'pokedex', pokemon_name)
        if os.path.exists(pokemon_website):
            return pokemon_website
        else:
            return None

    except Exception as e:
        print(e)
        
        
def get_all_pokemon_names(national_pokedex_url):
    
    national_pokedex_soup  = get_html_content(national_pokedex_url)
    
    # get names of all pokemon present on webpage here
    pokemon_names_html = national_pokedex_soup.find_all('a','ent-name')
    pokemon_names = [pokemon_name.text.strip() for pokemon_name in pokemon_names_html]
    
    pass

def get_pokemon_information(base_url, pokemon_name):
    pokemon_website = search_pokemon(base_url, pokemon_name)
    soup = get_html_content(pokemon_website)
    pass

get_all_pokemon_names(NATIONAL_POKEDEX_WEBSITE)