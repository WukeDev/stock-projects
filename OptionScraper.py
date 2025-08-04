import json
import os
import random
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from playwright.sync_api import sync_playwright, Locator, Page
import time
import threading

# File paths
folder = './optionsdata/' # subfolder to store local options data
tickers = ['SPX', 'SPY']
file_path = '%s%sdata-%s.csv'
address = 'https://researchtools.fidelity.com/ftgw/mloptions/goto/underlyingStatistics?cusip=&symbol=%s&Search=Search'
interval = 30

# Process locator text
def process(locator: Locator):
    return int(locator.text_content().strip().replace(',', '').replace('$', ''))

# Parse the page
def parse(page):
    price = float(page.locator('.main-number').text_content().strip("$ ").replace(',', ''))
    net_delta_calls = page.locator('tr:has(th#deltas) td:nth-of-type(1)')
    net_delta_puts = page.locator('tr:has(th#deltas) td:nth-of-type(2)')
    net_premium_calls = page.locator('tr:has(th#premium) td:nth-of-type(1)')
    net_premium_puts = page.locator('tr:has(th#premium) td:nth-of-type(2)')

    return [price, process(net_delta_calls), process(net_delta_puts), process(net_premium_calls), process(net_premium_puts)]

# Dash app for visualization
def launch_dash(update_period):
    app = Dash(__name__)
    
    app.layout = html.Div([
        dcc.DatePickerRange(
            id='date-range',
            max_date_allowed=pd.to_datetime('today').date(),
            initial_visible_month=pd.to_datetime('today').date(),
            start_date=pd.to_datetime('today').date(),
            end_date=pd.to_datetime('today').date(),
        ),
        dcc.Input(
            id='ticker',
            type='text',
            value='SPX',
            placeholder="ticker",
            debounce=True,
        ),
        html.Button('Update', id='update-button', n_clicks=0),
        dcc.Graph(id='delta-graph', config={"responsive": True}, style={'width': '100%', 'height': '100vh'}),
        dcc.Graph(id='premium-graph', config={"responsive": True}, style={'width': '100%', 'height': '100vh'}),
        dcc.Interval(
            id='interval-component',
            interval=update_period*1000,  # Update every update_period seconds
            n_intervals=0
        ),
    ])
    
    @app.callback(
        [Output('delta-graph', 'figure'),
         Output('premium-graph', 'figure')],
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('ticker', 'value'),
        Input('update-button', 'n_clicks'),
        Input('interval-component', 'n_intervals'),
    )
    def update_state(start_date, end_date, ticker, n_clicks, n_intervals):
        return update_graphs(start_date=start_date, end_date=end_date, ticker=ticker)

    # Run Dash server
    app.run(debug=False, host='0.0.0.0', port=8050, use_reloader=False)
        


# Function for obtaining a graph based on start date and end date from a csv file
def update_graphs(start_date, end_date, ticker: str, initial_df: pd.DataFrame=None):
        ticker.upper()
        date = pd.to_datetime(start_date).date()
        end_date = pd.to_datetime(end_date).date()
        dataframes = []
        if initial_df is not None:
            dataframes.append(initial_df)
        while date <= end_date:
            full_file_path = file_path % (folder, ticker, date)
            if os.path.exists(full_file_path):
                dataframes.append(pd.read_csv(full_file_path))
            date = date + pd.Timedelta(days=1)

        if len(dataframes) == 0:
            return go.Figure(), go.Figure()
        else:
            df = pd.concat(dataframes)
        
        # df['time'] = pd.to_datetime(df['time'], format='%H:%M:%S')

        # Delta Graph
        delta_fig = make_subplots(specs=[[{"secondary_y": True}], [{"secondary_y": True}]], rows=2, cols=1, shared_xaxes=True, vertical_spacing=0)
        delta_fig.add_trace(go.Scatter(x=df['time'], y=df['price'], yaxis='y1', mode='lines', name='Price', line=dict(color='white', width=1)), row=1, col=1, secondary_y=False)
        delta_fig.add_trace(go.Scatter(x=df['time'], y=df['net_delta_calls'], yaxis='y2', mode='lines', name='Net Delta Calls', line=dict(color='green', width=1)), row=1, col=1, secondary_y=True)
        delta_fig.add_trace(go.Scatter(x=df['time'], y=df['net_delta_puts'], yaxis='y2', mode='lines', name='Net Delta Puts', line=dict(color='red', width=1)), row=1, col=1, secondary_y=True)
        delta_fig.add_trace(go.Scatter(x=df['time'], y=df['price'], yaxis='y4', mode='lines', name='Price Bottom', line=dict(color='white', width=1)), row=2, col=1, secondary_y=False)
        delta_fig.add_trace(go.Scatter(x=df['time'], y=df['delta_momentum'], yaxis='y3', mode='lines', fill='tozeroy', name='Net Delta Momentum', line=dict(color='cyan', width=1), marker_color='cyan'), row=2, col=1, secondary_y=True)
        delta_fig.update_layout(
            title='Net Delta and Stock Price',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, zerolinecolor='black'),
            xaxis2=dict(showgrid=False, zerolinecolor='black'),
            yaxis=dict(showgrid=False, zeroline=False),
            yaxis2=dict(showgrid=False, zeroline=False),
            yaxis3=dict(showgrid=False),
            yaxis4=dict(showgrid=False, zeroline=False),
            plot_bgcolor='black',
            paper_bgcolor='black',
            font=dict(color='white'),
            uirevision=True,
            bargap=0,
            bargroupgap=0
        )

            # yaxis=dict(title='Stock Price', side='left', showgrid=False, zeroline=False),
            # yaxis2=dict(title='Net Premium (M)', side='right', overlaying='y', showgrid=False, zeroline=False),
            # yaxis3=dict(title='Premium Momentum (M)', side='right', overlaying='y', showgrid=False, color='Magenta'),
        # Premium Graph
        premium_fig = make_subplots(specs=[[{"secondary_y": True}], [{"secondary_y": True}]], rows=2, cols=1, shared_xaxes=True, vertical_spacing=0)
        premium_fig.add_trace(go.Scatter(x=df['time'], y=df['price'], yaxis='y1', mode='lines', name='Price', line=dict(color='white', width=1)), row=1, col=1, secondary_y=False)
        premium_fig.add_trace(go.Scatter(x=df['time'], y=df['net_premium_calls'], yaxis='y2', mode='lines', name='Net Premium Calls', line=dict(color='Chartreuse', width=1)), row=1, col=1, secondary_y=True)
        premium_fig.add_trace(go.Scatter(x=df['time'], y=df['net_premium_puts'], yaxis='y2', mode='lines', name='Net Premium Puts', line=dict(color='Crimson', width=1)), row=1, col=1, secondary_y=True)
        premium_fig.add_trace(go.Scatter(x=df['time'], y=df['price'], yaxis='y4', mode='lines', name='Price Bottom', line=dict(color='white', width=1)), row=2, col=1, secondary_y=False)
        premium_fig.add_trace(go.Scatter(x=df['time'], y=df['premium_momentum'], yaxis='y3', mode='lines', fill='tozeroy', name='Net Premium Momentum',line=dict(color='Magenta', width=1), marker_color='magenta'), row=2, col=1, secondary_y=True)
        premium_fig.update_layout(
            title='Net Premium and Stock Price',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False, zerolinecolor='black'),
            xaxis2=dict(showgrid=False, zerolinecolor='black'),
            yaxis=dict(showgrid=False, zeroline=False),
            yaxis2=dict(showgrid=False, zeroline=False),
            yaxis3=dict(showgrid=False),
            yaxis4=dict(showgrid=False, zeroline=False),
            plot_bgcolor='black',
            paper_bgcolor='black',
            font=dict(color='white'),
            uirevision=True,
            bargap=0,
            bargroupgap=0
        )

        return delta_fig, premium_fig

# Luanch scraper and wait until user logs in
def launch_scraper(address, ticker_arr, login_file=None, interval=5):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # add a script to bypass bot detection
        context.add_init_script('''const defaultGetter = Object.getOwnPropertyDescriptor(
            Navigator.prototype,
            "webdriver"
            ).get;
            defaultGetter.apply(navigator);
            defaultGetter.toString();
            Object.defineProperty(Navigator.prototype, "webdriver", {
            set: undefined,
            enumerable: true,
            configurable: true,
            get: new Proxy(defaultGetter, {
                apply: (target, thisArg, args) => {
                Reflect.apply(target, thisArg, args);
                return false;
                },
            }),
            });
            const patchedGetter = Object.getOwnPropertyDescriptor(
            Navigator.prototype,
            "webdriver"
            ).get;
            patchedGetter.apply(navigator);
            patchedGetter.toString();''')
        
        login_page = context.new_page()
        login_page.goto('https://digital.fidelity.com/prgw/digital/login/full-page')
        
        # If we want to prefill login
        if login_file is not None:
            with open(login_file, 'r') as file:
                login_data = json.load(file)
                login_page.get_by_label("Username", exact=True).fill(login_data["username"])
                login_page.get_by_label("Password", exact=True).fill(login_data["password"])
                login_page.get_by_role("button", name="Log in").click()
        
        login_page.wait_for_selector(".pbn", timeout=500000)
        
        scanner_pages = []
        for ticker in ticker_arr:
            individual_page = context.new_page()
            individual_page.goto(address % ticker)
            scanner_pages.append(individual_page)
        login_page.close()

        graph_page = browser.new_page()
        graph_page.goto('http://127.0.0.1:8050/')
        while True:
            start_time = time.time()
            
            # actions
            for scanner_page in scanner_pages:
                update_csv(scanner_page)
            
            end_time = time.time()
            wait_time = end_time - start_time
            if (wait_time < interval):
                time.sleep(interval - wait_time)
            
        return scanner_page, graph_page

# Update the csv file based on page data. Might remove dataframe dependency in the future
def update_csv(page: Page):
    current_date = pd.to_datetime('today').date()
    symbol = page.locator("input#symbol").get_attribute("value").upper()
    full_file_path = file_path % (folder, symbol, current_date)

    if not os.path.exists(folder):
        os.makedirs(folder)
        
    if os.path.exists(full_file_path):
        df = pd.read_csv(full_file_path)
    else:
        df = pd.DataFrame(columns=['time', 'price', 'net_delta_calls', 'net_delta_puts', 'net_premium_calls', 'net_premium_puts', 'delta_momentum', 'premium_momentum'])

    page.reload()
    row = parse(page)

    # Simulate randomness for testing
    # row[0] *= random.uniform(0.5, 1.5)
    # row[1] *= random.uniform(-0.1, 1.5)
    # row[2] *= random.uniform(-0.1, 1.5)

    # Add derived metrics
    row.append(row[1] + row[2])  # delta_momentum
    row.append(row[3] - row[4])  # premium_momentum
    current_time = pd.to_datetime('now').replace(microsecond=0)
    row.insert(0, current_time)

    # Update the DataFrame
    df.loc[len(df)] = row
    df.to_csv(full_file_path, index=False)
    return df


# Main entry point
if __name__ == '__main__':
    # Start Dash
    if not os.path.exists(folder):
        os.makedirs(folder)
        
    current_directory = os.path.dirname(os.path.realpath(__file__))
    login_file_path = os.path.join(current_directory, "login.json")
    dash_thread = threading.Thread(target=launch_dash, args=(interval,), daemon=True)
    scrape_thread = threading.Thread(target=launch_scraper, args=(address, tickers, login_file_path, interval))
    # Start threads
    dash_thread.start()
    scrape_thread.start()

    # Wait for both threads to complete
    scrape_thread.join()
    dash_thread.join()


