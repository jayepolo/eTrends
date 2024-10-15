import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from models import db, Vendor, PriceData

class Scraper:
    def __init__(self):
        self.url = "https://www.newenglandoil.com/rhodeisland/zone4.asp?x=0"
        self.logger = logging.getLogger(__name__)

    def parse_date(self, date_str):
        if not date_str or date_str == '\xa0':
            return datetime.now().date()  # Use current date if no date provided
        try:
            return datetime.strptime(date_str, '%m/%d/%Y').date()
        except ValueError:
            self.logger.warning(f"Could not parse date: {date_str}, using current date")
            return datetime.now().date()

    def parse_price(self, price_str):
        if not price_str or price_str == '\xa0':
            return None
        try:
            return float(price_str.replace('$', '').replace(',', ''))
        except ValueError:
            self.logger.warning(f"Could not parse price: {price_str}")
            return None

    def scrape(self):
        self.logger.info(f"Starting scrape from URL: {self.url}")
        response = requests.get(self.url)
        self.logger.info(f"Request status code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        self.logger.info("Successfully parsed HTML content")
        
        tables = soup.find_all('table')
        self.logger.info(f"Found {len(tables)} tables on the page")

        price_table = None
        for i, table in enumerate(tables):
            self.logger.info(f"Examining table {i+1}")
            headers = table.find_all('th') or table.find_all('tr')[0].find_all('td')
            header_text = ' '.join([h.text.strip() for h in headers])
            self.logger.info(f"Table {i+1} headers: {header_text}")
            
            if 'Company' in header_text and 'Price' in header_text:
                price_table = table
                self.logger.info(f"Found potential price table (Table {i+1})")
                break

        if not price_table:
            self.logger.error("Could not find a table with price data")
            raise Exception("Could not find the oil prices table")

        self.logger.info("Processing rows in the price table")
        rows = price_table.find_all('tr')[1:]  # Skip the header row
        self.logger.info(f"Found {len(rows)} data rows")
        
        for i, row in enumerate(rows, start=1):
            columns = row.find_all('td')
            if len(columns) >= 6:
                company_name = columns[0].text.strip()
                town = columns[1].text.strip()
                price = self.parse_price(columns[2].text.strip())
                date = self.parse_date(columns[5].text.strip())

                self.logger.info(f"Processing row {i}: Company: {company_name}, Town: {town}, Price: {price}, Date: {date}")

                if price is not None:
                    # Check if vendor exists, if not create a new one
                    vendor = Vendor.query.filter_by(name=company_name).first()
                    if not vendor:
                        vendor = Vendor(name=company_name, town=town)
                        db.session.add(vendor)
                        db.session.commit()
                        self.logger.info(f"Created new vendor: {company_name}")

                    # Check if price data already exists for this vendor and date
                    existing_price = PriceData.query.filter_by(vendor_id=vendor.id, date=date).first()
                    if existing_price:
                        self.logger.info(f"Price data already exists for {company_name} on {date}. Skipping.")
                        continue

                    # Add new price data
                    price_data = PriceData(vendor_id=vendor.id, price=price, date=date)
                    db.session.add(price_data)
                    self.logger.info(f"Added new price data for {company_name}: {price} on {date}")
                else:
                    self.logger.warning(f"Skipping row {i} due to missing price")

        db.session.commit()
        self.logger.info("Successfully committed all changes to database")
        self.logger.info("Scraping completed successfully")