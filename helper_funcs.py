import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
from faker import Faker

def get_gtfs(path_gtfs, files): 
    toReturn = []
    for i, file in enumerate(files): 
        toReturn.append(pd.read_csv(path_gtfs + file + ".txt", low_memory=False))
    return tuple(toReturn)

def get_poi(place_name, type): 
    tags = {"amenity": type}
    data = ox.geometries_from_place(place_name, tags)
    data = data[data.geometry.type == 'Point']

    data['latitude'] = data.geometry.y
    data['longitude'] = data.geometry.x

    return data[['latitude', 'longitude']].reset_index().drop('element_type', axis=1)

def get_pois(place_name, types):
    df_list = []
    for type in types:
        df = get_poi(place_name, type)
        df_list.append(df)
    concatenated_df = pd.concat(df_list, ignore_index=True)
    
    return concatenated_df

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371
    return c * r * 1000

def get_stops_win_dist(stops, poi_lat, poi_lon, distance, col_lat = "stop_lat", col_lon = "stop_lon"):
    stops.loc[:, 'dist_poi'] = stops.apply(lambda x: haversine(x[col_lat], x[col_lon], poi_lat, poi_lon), axis=1)
    return stops.loc[stops['dist_poi'] <= distance].copy()

def find_moc_stops(location, poi_names): 
    pd.options.mode.chained_assignment = None
    (stops, stop_times) = get_gtfs("gtfs/", ['stops', 'stop_times'])
    
    pois = get_pois(location, poi_names)
    print("Finding Mobility of Care stops for " + str(len(pois)) + " points of interest.")
    moc_stops = []
    for i, poi in pois.iterrows():
        nearby_stops = get_stops_win_dist(stops[['stop_id', 'stop_lat', 'stop_lon']], 
                                                       poi['latitude'], poi['longitude'], 
                                                       400, 
                                                       col_lat = "stop_lat", col_lon = "stop_lon")
        nearby_stops = nearby_stops.merge(stop_times[['stop_id', 'trip_id']], on='stop_id', how='left')
        idx_min_dist = nearby_stops.groupby('trip_id')['dist_poi'].idxmin()
        moc_stops += list(nearby_stops.loc[idx_min_dist, 'stop_id'].reset_index().stop_id.unique())
    stops['moc'] = stops['stop_id'].isin(moc_stops).astype(int)
    pd.options.mode.chained_assignment = 'warn'
    return stops

def get_list_active_cards(stages, njnys = 2): 
    unique_jny_keys_count = stages.groupby('CARD')['JNY_KEY'].nunique()
    # Filter the CARDS with more than 2 unique jny_keys
    return unique_jny_keys_count[unique_jny_keys_count >= njnys].index.tolist()

def get_stops_per_route(): 
    (stops, stop_times, trips, routes) = get_gtfs("gtfs/", ['stops', 'stop_times', 'trips', 'routes'])

    trip_route_map = trips[['trip_id', 'route_id']]
    stop_times_with_routes = stop_times.merge(trip_route_map, on='trip_id')
    stop_times_with_routes = stop_times_with_routes.merge(stops[['stop_id', 'stop_code']], on='stop_id').drop('stop_id', axis=1)
    stops_per_route = stop_times_with_routes.groupby('route_id')['stop_code'].apply(lambda x: list(x.unique())).reset_index()
    return stops_per_route.merge(routes[['route_id']], on='route_id')

"""
Functions to add columns
"""
def add_moc_col(stages, stops): 
    def label_journeys(df, moc_list):
        def is_moc(group):
            for _, row in group.iterrows():
                if row['stage_seq'] > 1 and row['start_place'] in moc_list:
                    return 1
            return 0

        # Group by JNY_KEY and apply the function to each group
        df['moc'] = df.groupby('jny_key').apply(lambda x: is_moc(x)).reset_index(level=0, drop=True)
        #df['END_TIME'] = df.groupby('JNY_KEY').apply(lambda x: )
        
        return df

    # Apply the function
    df_labeled = label_journeys(stages[['stage_seq', 'jny_key', 'start_place', 'end_place', 'subsystem']],
                                list(stops.loc[stops.moc == 1, 'stop_code'].values))
    df_labeled.loc[df_labeled.moc.isna(), 'moc'] = 0
    return df_labeled[['jny_key', 'moc']]

def add_route_col(stages):
    def find_route(row, routes_df):
        start = row['start_place']
        end = row['end_place']
        
        for _, route_row in routes_df.iterrows():
            stops = route_row['stop_code']
            if start in stops: 
                return route_row['route_id']
            if end in stops:
                return route_row['route_id']
        return None
        
    routes_with_stops = get_stops_per_route()
    stages['route'] = stages.apply(find_route, routes_df=routes_with_stops, axis=1).astype(str)
    return stages

def prep_stages_file(stages, stops): 
    stages.columns = [x.lower() for x in stages.columns]
    jnys_moc = add_moc_col(stages, stops)
    stages = add_route_col(stages)
    data = stages 

    print("Adding Trip Chaining...")
    #get the end time and route taken for previous stage within same journey key
    data.start_time = pd.to_datetime(data.start_time)
    data.end_time = pd.to_datetime(data.end_time)
    data['previous_end'] = data.groupby('jny_key').shift(1)['end_time']
    data['previous_route'] = data.groupby('jny_key').shift(1)['route']

    #calculate the transfer time
    data['transfer_time'] = data.start_time - data.previous_end
    data['transfer_time'] = data.transfer_time.apply(lambda x: round(x.total_seconds()/60,2))
    data['start_hour'] = data.start_time.dt.hour

    print("Adding MOC...")
    data = data.merge(jnys_moc.rename(columns={'JNY_KEY': 'jny_key'}), on='jny_key', how='left')
    return data

def create_journeys_file(data, stops, save_output = ''): 
    print("Recreating Journeys from stages...")
    subset = data
    journeys= subset.groupby('jny_key').count().reset_index()[['jny_key']]

    start= subset.groupby('jny_key').first()
    journeys['card'] = start.card.values
    journeys['moc'] = start.moc.values

    journeys['stages'] = start.num_stages.values
    journeys['start_place'] = start.start_place.values
    journeys['start_time'] = start.start_time.values
    journeys['start_hour'] = start.start_hour.values
    journeys['start_route'] = start.route.values
    del start

    end = subset.groupby('jny_key').last()
    journeys['end_place'] = end.end_place.values
    journeys['end_time'] = end.end_time.values
    journeys['end_route'] = end.route.values
    journeys['trip_time'] = journeys.end_time - journeys.start_time
    journeys['trip_time'] = journeys.trip_time.apply(lambda x: round(x.total_seconds()/60,2))
    journeys['distance'] = subset.groupby('jny_key').sum()['veh_meters'].values
    journeys['transfer_time'] = subset.groupby('jny_key').sum()['transfer_time'].values
    journeys['route_sequence'] = subset.groupby('jny_key')['route'].apply(' > '.join).values
    del end, subset

    journeys['start_time']= pd.to_datetime(journeys.start_time)
    journeys['end_time']= pd.to_datetime(journeys.end_time)
    journeys['weekday'] = journeys.start_time.dt.dayofweek
    journeys['weekday'] = np.where(journeys.weekday.isin([5,6]), 0, 1)
    journeys.sort_values(['card', 'start_time'], inplace= True)
    journeys.reset_index(inplace= True, drop= True)
    journeys['previous_end_time'] = journeys.groupby('card').shift(1)['end_time']
    journeys['previous_route'] = journeys.groupby('card').shift(1)['end_route']
    journeys['previous_start'] = journeys.groupby('card').shift(1)['start_place']
    journeys['previous_end'] = journeys.groupby('card').shift(1)['end_place']
    journeys['previous_duration'] = journeys.groupby('card').shift(1)['trip_time']
    journeys['previous_moc'] = journeys.groupby('card').shift(1)['moc']
    journeys['previous_transfer_time'] = journeys.groupby('card').shift(1)['transfer_time']
    journeys['restart_time'] = journeys.start_time - journeys.previous_end_time
    journeys['restart_time'] = journeys.restart_time.apply(lambda x: round(x.total_seconds()/60,2))
    journeys = journeys[journeys.restart_time > 0].reset_index(drop= True)

    #flag journeys where a restart occurs within 45 minutes of a MoC end place as MoC journeys
    journeys.at[(journeys.previous_end.isin(stops.stop_code.astype('str').values)) &
                (journeys.restart_time <= 45), 'previous_moc_flag'] = 1
    journeys['route_switch'] = np.where(journeys.start_route == journeys.previous_route, 0, 1)
    journeys['alt_moc_flag'] = journeys.moc
    journeys.loc[(journeys.previous_moc_flag == 1) &
                (journeys.restart_time <= 45), 'alt_moc_flag'] = 1
    journeys.loc[(journeys.previous_moc_flag == 1) &
                (journeys.restart_time <= 45), 'start_place'] = journeys.previous_start
    journeys.loc[(journeys.previous_moc_flag == 1) &
                (journeys.restart_time <= 45), 'trip_time'] = journeys.previous_duration + journeys.trip_time
    journeys.loc[(journeys.previous_moc_flag == 1) &
                (journeys.restart_time <= 45), 'transfer_time'] = journeys.transfer_time + journeys.restart_time + journeys.previous_transfer_time
    journeys.loc[(journeys.previous_moc_flag == 1) &
                (journeys.restart_time <= 45), 'route_sequence'] = journeys.previous_route+" > "+journeys.route_sequence

    journeys['in_vehicle_time'] = journeys.trip_time - journeys.transfer_time
    journeys['peak'] = np.where(journeys.start_hour.isin([6,7,8,9]), 'AM Peak',
                                np.where(journeys.start_hour.isin([15,16,17, 18]), 'PM Peak', 'Off Peak'))
    if save_output != '': 
        journeys.to_csv(save_output, index=False)

    return journeys

def find_top_moc_stops(journeys): 
    moc_df = journeys[journeys['moc'] == 1]

    moc_counts = moc_df['start_place'].value_counts()

    moc_counts_df = moc_counts.reset_index()
    moc_counts_df.columns = ['stop_code', 'moc_travelers']

    moc_counts_df = moc_counts_df.sort_values(by='moc_travelers', ascending=False)
    moc_counts_df.stop_code = moc_counts_df.stop_code.astype(int).astype(str)
    moc_counts_df = moc_counts_df.merge(get_gtfs("gtfs/", ['stops'])[0], on='stop_code', how='left')
    return moc_counts_df

def gen_fake_data(file_location = "fake_stages.csv", seed = 0): 
    fake = Faker()
    np.random.seed(seed)
    num_rows = 1000

    unique_jny_keys = [f'JNY_{i:06d}' for i in range(num_rows // 2)]
    jny_keys = unique_jny_keys + np.random.choice(unique_jny_keys, size=num_rows // 2, replace=False).tolist()
    np.random.shuffle(jny_keys)

    data = {
        'JNY_KEY': jny_keys,
        'SVC_DATE': [fake.date_time_this_decade().strftime('%d-%b-%y %H:%M:%S') for _ in range(num_rows)],
        'CARD': [fake.uuid4() for _ in range(num_rows)],
        'NUM_JNYS': np.random.randint(1, 5, size=num_rows),
        'JNY_SEQ': np.random.randint(1, 10, size=num_rows),
        'NUM_STAGES': np.random.randint(1, 5, size=num_rows),
        'STAGE_SEQ': np.random.randint(1, 10, size=num_rows),
        'SUBSYSTEM': np.random.choice(['bus', 'rail'], size=num_rows),
        'START_PLACE': np.random.choice(get_gtfs('gtfs/', ['stops'])[0].stop_code.values, size=num_rows),
        'END_PLACE': np.random.choice(get_gtfs('gtfs/', ['stops'])[0].stop_code.values, size=num_rows),
        'START_TIME': [fake.date_time_this_decade().strftime('%d-%b-%y %H:%M:%S') for _ in range(num_rows)],
        'END_TIME': [fake.date_time_this_decade().strftime('%d-%b-%y %H:%M:%S') for _ in range(num_rows)],
        'VEH_METERS': np.random.uniform(1000, 20000, size=num_rows),
        'VEH_SEC': np.random.uniform(600, 3600, size=num_rows)
    }

    df = pd.DataFrame(data)
    df.to_csv(file_location, index=False)
    return df