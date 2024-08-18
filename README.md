
#  <img width="153" alt="image" src="https://github.com/user-attachments/assets/3c194852-64d2-4980-a86f-679329e8ea08">  HomeBound: A Mobility of Care Tool

## Description
Public transportation in the U.S. has been designed to serve worker travel patterns. However, only [18% of urban mobility](https://nhts.ornl.gov/assets/2017_nhts_summary_travel_trends.pdf) trips are for the purpose of work. Further, post-pandemic, the proportion of trips taken for the purpose of work is [decreasing](https://nhts.ornl.gov/). To boost ridership and more equitably serve their communities, public transportation agencies should consider planning for non-work travel patterns. 

One common type of non-work travel pattern is travel for the purpose of the household or Mobility of Care (i.e. dropping of the children or picking up the groceries or attending household administrative appointments). Mobility of Care trips are [characterized](https://findingspress.org/article/75352-can-mobility-of-care-be-identified-from-transit-fare-card-data-a-case-study-in-washington-d-c) with higher rates of inconvenient travel, particularly shorter overall distances but longer travel times. Planning for Mobility of Care trips is critical to adapt to the changing travel needs in cities across the country. 

Classifying travel purposes from proves analytically challenging. The current methods to identify travel purposes rely on survey data, prone to bias and limited in scope of analysis. Big data is an opportunity to offer more granular planning recommendations to transit agencies across the globe, especially for more general household travel purposes. 

## Description
HomeBound is a travel purpose-identification tool for public transportation agencies around the globe to identify journeys of individuals travelling for the purpose of the household. HomeBound offers analytical tools to evaluate trips identified as Mobility of Care, using visuals and an interactive tool (see the appendix). HomeBound is the first step towards using big data to examine the transport system through a gendered lens. HomeBound should be used by transportation planners and transportation policy makers who are seeking insight into the travel purposes of their riders and constituents. This application can be used by any transit agency. 

## Getting Started

### Dependencies

- GTFS: A [GTFS](https://gtfs.org/) folder containing the stops.txt, stop_times.txt, routes.txt, and trips.txt (obtainable from publically accessible GTFS sources) is required. 
- Python: The code is run using Python. You can download python [here]([https://posit.co/download/rstudio-desktop/](https://www.python.org/downloads/). 
- Download the code using git
    ```
    git clone https://github.com/dshuman/mobility_of_care_tool.git
    ```
    or by downloading directly. Hit Code > download .zip. Once the .zip is downloaded, move the .zip into your disired directory and extract zip by rightclicking and hitting extract. 

### Executing program

Once Pyton has been installed, download this code. By default, the code searches for the data in the existing directory as the downloaded code.

#### Running the Code

In order to run, there are three required parameters: 
- `location`: contains the name of the city for which the analysis is run
- `poi_names`: contains a list of the names of the types of Points of Interest included in this analysis. 
- `only_active`: a boolean for whether or not to only limit the riders to active riders
- `input_stages_file`: *(optional)* Default is set to a randomly generated file (in `helper_funcs.py > gen_fake_data()`)
- `output_journeys_file`: the desired name of the output classification file
- `moc_stops_file`: *(optional)* Default is a file generated using GTFS and OSM (in `helper_funcs.py > find_moc_stops()`)
      
Here is an example of inputted parameters. 
```
location = "Washington D.C."
poi_names = ['kindergarten', 'school']
only_active = False
input_stages_file = ''
output_journeys_file = 'journeys_w_moc.csv'
moc_stops_file = ''
```

