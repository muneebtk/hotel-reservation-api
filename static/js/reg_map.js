let map;
let marker;
let locationInput;
let geocoder;

function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: 23.6345, lng: 58.7410 }, // Coordinates for Oman
        zoom: 6, 
        mapTypeControl: false, 
        streetViewControl: false, 
    });

    geocoder = new google.maps.Geocoder();

    // Initialize location input field
    locationInput = document.getElementById('hotelAddress');

    // Add input event listener to the location field
    // locationInput.addEventListener('input', function() {
    //     searchAddress(locationInput.value);
    // });

    // Add click event listener to map
    map.addListener('click', function(event) {
        placeMarker(event.latLng);
        updateLocationInput(event.latLng);
    });
}

function placeMarker(latLng) {
    // If there's an existing marker, remove it
    if (marker) {
        marker.setMap(null);
    }

    // Create a new marker with a red color
    marker = new google.maps.Marker({
        position: latLng,
        map: map,
        icon: {
            url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png" // Google Maps built-in red dot icon
        }

    });
}

function updateLocationInput(latLng) {
    // Use geocoder to convert latLng to address
    geocoder.geocode({ 'location': latLng }, function(results, status) {
        if (status === 'OK') {
            if (results[0]) {
                // Set the address in the location input field
                locationInput.value = results[0].formatted_address;

                // Extract address components
                const addressComponents = results[0].address_components;

                // Initialize empty variables for address components
                let stateProvince = '';
                let city = '';
                let country = '';

                // Loop through address components to find state, city, and country
                for (let component of addressComponents) {
                    if (component.types.includes('administrative_area_level_1')) {
                        stateProvince = component.long_name;
                    } else if (component.types.includes('locality')) {
                        city = component.long_name;
                    } else if (component.types.includes('country')) {
                        country = component.long_name;
                    }
                }

                // Update the respective input fields
                document.getElementById('stateProvince').value = stateProvince;
                document.getElementById('city').value = city;
                document.getElementById('country').value = country;

            } else {
                locationInput.value = 'No results found';
            }
        } else {
            locationInput.value = 'Geocoder failed due to: ' + status;
        }
    });
}


// function searchAddress(address) {
//     if (!address) {
//         // If the address field is empty, return
//         return;
//     }
    
//     geocoder.geocode({ 'address': address }, function(results, status) {
//         if (status === 'OK') {
//             if (results[0]) {
//                 const location = results[0].geometry.location;
//                 map.setCenter(location);
//                 placeMarker(location);
//                 locationInput.value = results[0].formatted_address;
//             } else {
//                 locationInput.value = 'No results found';
//             }
//         } else if (status === 'ZERO_RESULTS') {
//             locationInput.value = 'No results found for this address. Please try a different address.';
//         } else {
//             locationInput.value = 'Geocoder failed due to: ' + status;
//         }
//     });
// }

