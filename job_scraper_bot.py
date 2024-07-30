import asyncio

import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def scrape_github_internships(url: str, max_retries: int = 5,
                                    retry_delay: int = 5) -> pd.DataFrame:
    async with aiohttp.ClientSession() as session:
        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()
                    html = await response.text()

                soup = BeautifulSoup(html, 'html.parser')

                content = soup.find('article', class_='markdown-body entry-content container-lg')
                if not content:
                    logger.warning("Could not find the content container")
                    return pd.DataFrame()

                table = content.find('table')
                if not table:
                    logger.warning('No table found')
                    return pd.DataFrame()

                headers = [th.text.strip() for th in table.find_all('th')]

                unique_rows = set()
                rows = []

                for tr in table.find_all('tr')[1:]:
                    row = []
                    skip_row = False

                    for i, td in enumerate(tr.find_all('td')):
                        if '🔒' in td.text:
                            skip_row = True
                            break

                        link = td.find('a')
                        if link and link.has_attr('href'):
                            if i == 0 and link.text.strip():
                                row.append(link.text.strip())
                            else:
                                row.append(link['href'])
                        else:
                            row.append(td.text.strip())

                    if not skip_row:
                        row_tuple = tuple(row)
                        if row_tuple not in unique_rows:
                            unique_rows.add(row_tuple)
                            rows.append(row)

                df = pd.DataFrame(rows, columns=headers)

                return df

            except Exception as e:
                logger.error(f"Error scraping {url} (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Max retries reached. Scraping failed.")
                    return pd.DataFrame()

    return pd.DataFrame()


def sort_dataframe_by_date(df: pd.DataFrame) -> pd.DataFrame:
    date_column = 'Date Posted'

    if date_column not in df.columns:
        logger.warning(f"'{date_column}' column not found in the DataFrame")
        return df

    date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y', '%b %d', '%b %d, %Y']

    def parse_date(date_str):
        for date_format in date_formats:
            try:
                return pd.to_datetime(date_str, format=date_format)
            except ValueError:
                continue
        return pd.NaT

    df[date_column] = df[date_column].apply(parse_date)

    df_sorted = df.sort_values(by=date_column, ascending=True)

    return df_sorted
