import re
from math import floor
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import html
import yfinance as yf
from matplotlib import pyplot as plt

headers = {
    'Connection': 'close',
    'Accept': 'application/json, text/javascript,application/xml,text/xml */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'
}

# This Method gets all the xml links for a given URL
def get_xml_links(url):
    # Make a request to the page
    response = requests.get(url, headers=headers)
    # Parse the HTML source code using lxml
    tree = html.fromstring(response.content)
    # Find the link to the first XML file on the page
    links = tree.xpath('//a/@href')
    # Print the link to the XML file
    xml_links = [link for link in links if 'xml' in link]
    if len(xml_links) == 0:
        return 0
    return xml_links[0]

def get_form4_information(cik):
    #This method returns all the form4 filling information of a cik,
    #We can make it get the from any number to all the fillings for a cik
    cik = str(cik)
    url = "https://www.sec.gov/Archives/edgar/data/" + cik
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    filing_links = []
    for row in soup.find_all('tr'):
        filing_links.append(row.find_all('a')[0]['href'])
    filing_links = filing_links[1:]
    hist_data = get_form4_for_one_link(filing_links[0])
    #retrieving the last 100 fillings
    for link in filing_links[1:700]:
        hist_data = pd.concat([hist_data, get_form4_for_one_link(link)], ignore_index=True)

        #returns the stock info as a dataframe
    return hist_data


    #This method gets the form4 filling for one link
def get_form4_for_one_link(filing_link):


    # get the xml link from the form4 filling link
    xml_link = get_xml_links("https://www.sec.gov" + filing_link)
    if xml_link == 0:
        return
    response = requests.get("https://www.sec.gov" + xml_link, headers=headers)
    # Parse the response using BeautifulSoup
    soup = BeautifulSoup(response.content, 'xml')
    if soup.find('issuerCik') == None or soup.find('transactionDate') == None:
        return
    # Extract the company information
    issuer_cik = soup.find('issuerCik').text.strip()
    issuer_name = soup.find('issuerName').text.strip()
    owner_name = soup.find('rptOwnerName').text.strip()
    issuer_trading_symbol = soup.find('issuerTradingSymbol').text.strip()
    # Extracting important elements
    transaction_date = soup.find('transactionDate').text.strip()
    transaction_shares = soup.find('transactionShares').text.strip()
    transaction_price_per_share = soup.find('transactionPricePerShare').text.strip()
    regex = re.compile('(securityTitle|underlyingSecurityTitle)')
    underlying_security_title = soup.find(regex).text.strip()
    shares_owned_following_transaction = soup.find('sharesOwnedFollowingTransaction').text.strip()
    ownership_nature = soup.find('ownershipNature').find('directOrIndirectOwnership').text.strip()
    form4_dict = {
        'issuer_cik': issuer_cik,
        'issuer_name': issuer_name,
        'issuer_trading_symbol': issuer_trading_symbol,
        'transaction_date': transaction_date,
        'transaction_shares': transaction_shares,
        'transaction_price_per_share': transaction_price_per_share,
        'owner_name':owner_name,
        'underlying_security_title': underlying_security_title,
        'shares_owned_following_transaction': shares_owned_following_transaction,
        'ownership_nature': ownership_nature
    }
    form4_dict = pd.DataFrame.from_dict([form4_dict])
    form4_dict['transaction_date'] = pd.to_datetime(form4_dict['transaction_date'],utc=True)
    form4_dict['transaction_date'] = form4_dict['transaction_date'].dt.tz_localize(None)
    form4_dict.dropna(inplace=True)
    form4_dict.reset_index(inplace=True, drop=True)

    #returns a dictionary holding the processed form4 information
    return form4_dict


#Return of historical stock prices for a symbol
def get_stock_prices(symbol, start_date, end_date):
    stock = yf.Ticker(symbol)
    prices = stock.history(start=start_date, end=end_date)
    prices.reset_index(inplace=True)
    prices.rename(columns={'Date': 'transaction_date'}, inplace=True)
    prices['transaction_date'] = pd.to_datetime(prices['transaction_date'], utc=True)
    prices.loc['transaction_date'] = prices['transaction_date'].dt.strftime('%Y-%m-%d')
    prices['transaction_date'] = prices['transaction_date'].dt.tz_localize(None)
    prices['transaction_date'] = prices['transaction_date'].dt.normalize()
    prices['transaction_date'] = prices['transaction_date'].dt.floor('D')
    prices.reset_index(inplace=True,drop=True)

    #returns the historical prices as a dataframe
    return prices

#This function extracts multiple companies’ data a time
def get_multiple_companies(list_of_ciks):
    for i in list_of_ciks:
        stock = get_form4_information(i)
        stock.to_csv(str(stock['issuer_trading_symbol'][0])+'_formdata.csv')


#Test case for AAPL CIK:
form4_df = get_form4_information(320193)
start_date = form4_df['transaction_date'].min()
end_date = form4_df['transaction_date'].max()
symbol = form4_df['issuer_trading_symbol'][0]
historical_prices = get_stock_prices(symbol, start_date, end_date)

#Merging the form4 transaction prices per share against the stock market prices based on transaction date.
merged_df = pd.merge(form4_df, historical_prices, on='transaction_date', how='inner')
merged_df['Average'] = (merged_df['Open'] + merged_df['High'] + merged_df['Low'] + merged_df['Close']) / 4

#sorting in descending order
merged_df = merged_df.sort_values(by='transaction_date', ascending=False)
print(merged_df.loc(axis=1)['transaction_date', 'Average','transaction_price_per_share','transaction_shares'].to_csv('historical_data.csv'))
print(merged_df.shape,merged_df.head())
merged_df.dropna(inplace=True)
print(merged_df.shape,merged_df.head())

#Plot of historical and form4 data
# plot the two columns on the y-axis against the date column on the x-axis
plt.plot(merged_df['transaction_date'], merged_df['transaction_price_per_share'], label='transaction_price_per_share from Form4'+symbol)
plt.plot(merged_df['transaction_date'], merged_df['Average'], label='Average(High, Low, Open, Close Prices')
# set the title and axis labels
plt.title('Comparison of Historical data for: '+symbol)
plt.xlabel('Date')
plt.ylabel('Prices')
# pl.xticks([])
x1 = merged_df['transaction_price_per_share'].max()
x2 = merged_df['Average'].max()


print(f"The Maximum transaction price per share for: {symbol} form form 4 fillings was: {x1}")
print(f"The Average price per share for: {symbol} from history was: {x2}")
max_price = floor(max(float(x1),float(x2)))
max_price = floor(max_price)
# set the number of ticks to display on the y-axis
num_ticks = 10
yticks = np.linspace(0, max_price, num_ticks)
plt.yticks(yticks)
# add a legend to the plot
plt.legend()
# show the plot
plt.show()
#Get multiple companies at once
ciks =[1318605,320193,1045810,1018724,789019,1326801,1652044,1682852,1647639,1535527,1818874,1783879,1633917,1559720,2488]
get_multiple_companies(ciks)

