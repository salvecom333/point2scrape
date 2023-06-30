import requests
from bs4 import BeautifulSoup
import csv
import re
from tqdm import tqdm
import math

BASE = 'https://www.point2homes.com/'
HEADERS = { 'Accept':'application/json, text/javascript, */*; q=0.01',
           'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36',}
#url = input(f'What is your url?')
while True:
    url = input(f'What is your url?')
    if url[:4] != 'http':
        print('Type a correct URL!')
    else:
        break
inp_fn = input("What do you want to name your file results?") + ".csv"
PARAMS ={'page': None}

dict_pages = {'pages': None}

def extract(page = 1):
    '''
    Extract `listings` in `soup` for each page
    '''
    # (prep for) GET request

    params = PARAMS.copy()
    params['page'] = page

    r = requests.get(url=url, params=params, headers=HEADERS)

    # get listings per page
    soup = BeautifulSoup(r.content, 'html5lib')

    # get indication pages; each page has max. 24 entries
    if page == 1:
        entries = int(soup.find('div', class_='pager_title_section')\
                      .get_text().split()[0])
        max_entries_per_page = 24
        dict_pages['pages'] = math.ceil(entries/max_entries_per_page)

    # progress prints
    print(f'Getting page {page} of {dict_pages["pages"]}. Processing data...',
          end='\n')


    listings = soup.find_all('article')
    # check if page contains a `next` elem
    if soup.find('a', class_='pager-next'):
        _next = page + 1
        #if page > dict_pages['pages']:
            #return listings, None
        return listings, _next
    return listings, None

def add_info(href_listing):
  r = requests.get(url=f'{BASE}{href_listing}', headers=HEADERS)
  soup = BeautifulSoup(r.content, 'html5lib')
  hidden_lat = soup.find('input', {"name":re.compile('^Latitude')})
  lat = str(hidden_lat).split("=")[4].replace('/>', '').replace('"','')
  hidden_lon = soup.find('input', {"name":re.compile('^Longitude')})
  lon = str(hidden_lon).split("=")[4].replace('/>', '').replace('"','')
  coord = lat, lon
  map = f"https://maps.google.com/?q={lat},{lon}"
  #print(map)
  try:
      phone_tag = soup.find_all("span", {"class": "ic-phone shownumber", "data-phone":True})
      phone_numbers = ([s["data-phone"] for s in phone_tag])
      #print(phone_numbers)
      #cell_number = getattr(phone, 'data-phone')
     # print(cell_number)
  except:
      phone_numbers = "Phone not found"
  try:
      image = soup.find("a", {"rel": "noopener"}).img['src']
      #imagex = ([s["data-src"] for s in images])
      #print(image)
  except:
      image = "No image"
  info_link = (f'{BASE}{href_listing}')
  return [map, phone_numbers, image, info_link]

def extract_agent(href_listing):
    '''
    Extracts agent, firm as `list`. Used if such info not available on main page.
    '''
    # GET request, soup, extract agent, firm (firm may be `None`)
    r = requests.get(url=f'{BASE}{href_listing}', headers=HEADERS)
    soup = BeautifulSoup(r.content, 'html5lib')
    agent = soup.find('div', class_='agent-details-top').div.get_text(strip=True)
    firm = soup.find('div', class_='agent-details-top').p
    if firm:
        firm = firm.get_text(strip=True)
    return [agent, firm]

def transform(ls):
    '''
    Returns a `list` ('r_list'), i.e. a "row" to be passed to func `writer`.
    '''
    # initialize list
    r_list = list()

    # get `address` (use `get_text(strip=True)` instead of
    # `.text.replace('\n', "").strip()` here and elsewhere)
    address = ls.find('div', class_='address-container').get_text(strip=True)
    r_list.append(address)

    # get `beds, baths, size, area, acres`
    labels = ['Beds?', 'Baths?', 'Sqft', 'property-type ic-proptype', 'Lot Size']

    for label in labels:
        if label != 'property-type ic-proptype':
            label_item = ls.find('li', {'data-label': re.compile(label)})
            if label_item:
                # the actual measurement will be first elem in split
                # on `<strong>`, replace ',' with '' to get numeric
                label_item = label_item.strong.get_text(strip=True).split()[0]\
                    #.replace(',','')
                r_list.append(label_item)
            else:
                # info not found
                r_list.append(None)
        else:
            # handle `area` differently
            area = ls.find('li', class_='property-type ic-proptype')\
                          .get_text(strip=True)
            r_list.append(area)

    # get `price`, extract only part with digits, and replace ',' with ''
    # I.e. *these* listings at least are *all* in "USD"
    #r_list.append(ls.find('div', class_='price')['data-price'])
    price = ls.find('div', class_='price')['data-price'].replace(',','').replace('$','').replace('USD','')
    r_list.append(price)
    # alternative for `price`, if you just want whole string:
        #r_list.append(ls.find('div', class_='price')['data-price'])
    # or maybe try to split `amount` and `currency` in diff columns

    # get `agent, firm`
    agents = ['agent-name', 'agent-(?=item-company|company)']

    for agent in agents:
        agent_item = ls.find('div', {'class': re.compile(agent)})
        if agent_item:
            agent_item = agent_item.get_text(strip=True)
            r_list.append(agent_item)

    # numerous listings only have `agent, firm` on the actual listing page
    if len(r_list) == 7:
        # if `True`, nothing was added, so get `href` and check listing page
        href_listing = ls.select_one('a[href]')['href']
        r_list.extend(extract_agent(href_listing))
    href_listing = ls.select_one('a[href]')['href']
    r_list.extend(add_info(href_listing))

    return r_list

def writer(listings, add_header = False):
    '''
    Writes data per listing captured in `r_list` as single rows to csv file.
    '''
    #inp_fn = input("What do you want to name your file results?") + ".csv"

    fname = inp_fn

    # N.B. mode should be `a` (append);
    # with `w` you would overwrite the file each time
    with open(file = fname, mode = 'a', encoding = 'utf8', newline= '') as f:
        thewriter = csv.writer(f)

        # only add the header at the start
        if add_header == True:
            header = ['Address', 'Beds', 'Baths', 'Size', 'Area', 'Acres',
                      'Price', 'Agent', 'Firm', 'Map', 'Contact', 'Picture',
                      'Listing Link']
            thewriter.writerow(header)

        # get `row` per listing and append to csv
        for ls in tqdm(listings):
            r_list = transform(ls)
            thewriter.writerow(r_list)
    if not _next:
        print(f'\n{fname} created')
    return _next

if __name__ == '__main__':
    # get listings per page. We'll stop after p. 7, where `_next` == `None`
    listings, _next = extract()
    _next = writer(listings, add_header=True)
    while _next:
        #if _next == 'None':
          #break
        listings, _next = extract(_next)
        #if _next == 'None':
            #break
        _next = writer(listings)
