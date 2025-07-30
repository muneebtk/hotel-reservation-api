//promocode_exist

function showRelevantFields() {
    const category = document.getElementById("category").value;

    document.getElementById("common_fields").style.display = "none";
    document.getElementById("promo_code_fields").style.display = "none";
    document.getElementById("targeted_fields").style.display = "none";
    document.getElementById("seasonal_event_fields").style.display = "none";
    document.getElementById("loyalty_program_fields").style.display = "none";

    switch (category) {
        case "common":
            document.getElementById("common_fields").style.display = "block";
            break;
        case "promo_code":
            document.getElementById("promo_code_fields").style.display = "block";
            break;
        case "targeted_offers":
            document.getElementById("targeted_fields").style.display = "block";
            break;
        case "seasonal_event":
            document.getElementById("seasonal_event_fields").style.display = "block";
            break;
        case "loyalty_program":
            document.getElementById("loyalty_program_fields").style.display = "block";
            break;
    }
}

function validateForm() {
    document.querySelectorAll('.error-message').forEach(el => {
        el.style.display = 'none';
        el.querySelector('small').innerText = '';
    });

    const category = document.getElementById("category").value;

    const offerName = document.getElementById("offer_name");
    const description = document.getElementById("description");
    const discountValue = document.getElementById("discount_value");
    const discountPercentage = document.getElementById("discount_percentage");

    // Offer Name Validation
    if (!offerName.value.trim()) {
        showError(offerName, "Offer Name is required.");
        return false;
    }

    if (offerName.value.trim().length > 255) {
        showError(offerName, "Offer Name cannot exceed 255 characters.");
        return false;
    }

    // Description Validation
    if (!description.value.trim()) {
        showError(description, "Description is required.");
        return false;
    }

    if (description.value.trim().length > 1000) {
        showError(description, "Description cannot exceed 1000 characters.");
        return false;
    }

    // Discount Validation
    if (!discountValue.value.trim() && !discountPercentage.value.trim()) {
        showError(discountValue, "You need to enter discount percentage or discount value to proceed.");
        return false;
    }

    if (discountValue.value && parseFloat(discountValue.value) <= 0) {
        showError(discountValue, "Please enter a valid discount value.");
        return false;
    }

    if (discountPercentage.value && parseFloat(discountPercentage.value) <= 0) {
        showError(discountPercentage, "Please enter a valid discount percentage.");
        return false;
    }

    switch (category) {
        case "common":
            // Common category validations
            const minimumSpend = document.getElementById("minimum_spend");
            const validityFrom = document.getElementById("validity_from");
            const validityTo = document.getElementById("validity_to");

            // Ensure minimum spend does not allow decimals
            const minimumSpendValue = minimumSpend.value.trim();
            if (!/^\d+$/.test(minimumSpendValue)) {
                showError(minimumSpend, "Minimum spend must be a whole number (no decimals).");
                return false;
            }

            if (parseInt(minimumSpendValue) <= 0) {
                showError(minimumSpend, "Please enter a valid minimum spend.");
                return false;
            }

            if (!validityFrom.value) {
                showError(validityFrom, "Please specify a valid start date.");
                return false;
            }

            if (!validityTo.value) {
                showError(validityTo, "Please specify a valid end date.");
                return false;
            }

            const currentDate = new Date();
            currentDate.setHours(0, 0, 0, 0);
            const fromDate = new Date(validityFrom.value);
            fromDate.setHours(0, 0, 0, 0);
            const toDate = new Date(validityTo.value);
            toDate.setHours(0, 0, 0, 0);

            if (fromDate < currentDate) {
                showError(validityFrom, "'Valid From' date cannot be in the past.");
                return false;
            }
            if (toDate < currentDate) {
                showError(validityTo, "'Validity To' date cannot be in the past.");
                return false;
            }
            if (fromDate > toDate) {
                showError(validityFrom, "Start date cannot be later than the end date.");
                return false;
            }
            break;

            case "promo_code":
            // Promo code validations
            const promoCode = document.getElementById("promo_code");
            const maxUses = document.getElementById("max_uses");
            const promo_validity_from = document.getElementById("promo_validity_from");
            const promo_validity_to = document.getElementById("promo_validity_to");

            if (!promoCode.value.trim()) {
                showError(promoCode, "Promo code is required.");
                return false;
            }

            if (promoCode.value.trim().length > 50) {
                showError(promoCode, "Promo code cannot exceed 50 characters.");
                return false;
            }

            const maxUsesValue = parseInt(maxUses.value);
            if (isNaN(maxUsesValue) || maxUsesValue <= 0) {
                showError(maxUses, "Please specify a valid number of max uses.");
                return false;
            }
            if (!promo_validity_from.value) {
                showError(promo_validity_from, "Please specify a valid date.");
                return false;
            }

            if (!promo_validity_to.value) {
                showError(promo_validity_to, "Please specify a valid date.");
                return false;
            } 
            const promocurrentDate = new Date();
            promocurrentDate.setHours(0, 0, 0, 0);
            const promofromDate = new Date(promo_validity_from.value);
            promofromDate.setHours(0, 0, 0, 0);
            const promotoDate = new Date(promo_validity_to.value);
            promotoDate.setHours(0, 0, 0, 0);
            if (promofromDate < promocurrentDate) {
                showError(promo_validity_from, "'Valid From' date cannot be in the past.");
                return false;
            }
            if (promotoDate < promocurrentDate) {
                showError(promo_validity_to, "'Validity To' date cannot be in the past.");
                return false;
            }

            if (new Date(promo_validity_from.value) > new Date(promo_validity_to.value)) {
                showError(promo_validity_from, "Start date cannot be later than end date.");
                return false;
            }
            break;

        case "targeted_offers":
            const targetedType = document.getElementById("targeted_type");
            if (!targetedType.value) {
                showError(targetedType, "Please select a targeted offer type.");
                return false;
            }
            break;

        case "seasonal_event":
            const occasionName = document.getElementById("occasion_name");

            if (!occasionName.value.trim()) {
                showError(occasionName, "Occasion name is required.");
                return false;
            }

            if (!isNaN(occasionName.value.trim())) {
                showError(occasionName, "Occasion name cannot be a number.");
                return false;
            }

            if (occasionName.value.trim().length > 100) {
                showError(occasionName, "Occasion name cannot exceed 100 characters.");
                return false;
            }
            break;

        case "loyalty_program":
            const pointsRequired = document.getElementById("points_required");

            const pointsRequiredValue = parseInt(pointsRequired.value);
            if (isNaN(pointsRequiredValue) || pointsRequiredValue <= 0) {
                showError(pointsRequired, "Please specify the points required.");
                return false;
            }
            break;
    }

    return true;
}


function showError(inputElement, message) {
    const errorSpan = inputElement.parentNode.querySelector('.error-message');

    if (errorSpan) {
        errorSpan.style.display = 'block';
        errorSpan.querySelector('small').innerText = message;
        }
    }
function reloadcreate() {
    var discount = document.getElementById("category").value;
    var page =   1;
    $('#select_discount').val(discount);
    setTimeout(function() {
        $.ajax({
        url: '/vendor/save_offer/filter/',
        type: 'GET',
        headers: {
            'X-CSRFToken': window.CSRF_TOKEN
        },
        data: {
            "discount": discount,
            "page": page
        },
        success: function (data) {
            $('#hotelTable').removeClass('blurred');
            $('#loader').hide();
            $('table thead').html($(data).find('thead').html());
            $('table tbody').html($(data).find('tbody').html());
            $('.pagination').html($(data).find('.pagination').html());
            const rows = $(data).find('table tbody tr');
            const totalRows = rows.length;

            const currentPage = parseInt($('.current-page').text(), 10) || 1;

            if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 10)) {
                $('.pagination').hide();
            } else {
                $('.pagination').html($(data).find('.pagination').html()).show();
            }     
        },
        error: function (xhr, status, error) {
            console.error('Error fetching data:', error);
            alert('Error fetching pagination data. Please try again later.');

            $('#loader').hide();
            $('#hotelTable').removeClass('blurred');
        }
    });
    }, 500); 
}

$('#vendoruserOfferForm').on('submit', function (e) {
e.preventDefault();  

if (!validateForm()) {
    return;  
}

var form = $(this);
var formData = form.serialize();  // Serialize form data

$('#loader').show();
$('#hotelTable').addClass('blurred');

$.ajax({
    url: form.attr('action'),
    type: 'POST',
    headers: {
        'X-CSRFToken': window.CSRF_TOKEN
    },
    data: formData,  
    success: function (data) {
        $('#loader').hide();
        $('#hotelTable').removeClass('blurred');
        reloadcreate();
        document.getElementById('id03').style.display = 'none';
        $('#vendoruserOfferForm')[0].reset();

    },
    error: function (xhr, status, error) {
        console.error('Error submitting form:', error);
        alert('Error submitting the form. Please try again later.');

        $('#loader').hide();
        $('#hotelTable').removeClass('blurred');
        document.getElementById('id03').style.display = 'none';

    }
});
});


function w3_open() {
document.getElementById("mySidebar").style.display = "block";
document.getElementById("myOverlay").style.display = "block";
}

function w3_close() {
document.getElementById("mySidebar").style.display = "none";
document.getElementById("myOverlay").style.display = "none";
}

document.addEventListener('DOMContentLoaded', function () {
    var openModalButton = document.getElementById('openModalButton');
    var modal = document.getElementById('id03');

    openModalButton.addEventListener('click', function () {
        modal.style.display = 'block';
    });

    window.onclick = function (event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
});


function reload() {
    var discount = $('.select_discount').val();
    var page =  parseInt($('.current-page').text(), 10) || 1;

  
    setTimeout(function() {
        $.ajax({
        url: '/vendor/save_offer/filter/',
        type: 'GET',
        headers: {
            'X-CSRFToken': window.CSRF_TOKEN
        },
        data: {
            "discount": discount,
            "page": page
        },
        success: function (data) {
            $('#hotelTable').removeClass('blurred');
            $('#loader').hide();
            $('table thead').html($(data).find('thead').html());
            $('table tbody').html($(data).find('tbody').html());
            $('.pagination').html($(data).find('.pagination').html());
            const rows = $(data).find('table tbody tr');
            const totalRows = rows.length;

            // Find the current page number based on the 'current-page' class
            const currentPage = parseInt($('.current-page').text(), 10) || 1;

            if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 10)) {
                $('.pagination').hide();
            } else {
                $('.pagination').html($(data).find('.pagination').html()).show();
            }
        },
        error: function (xhr, status, error) {
            console.error('Error fetching data:', error);
            alert('Error fetching pagination data. Please try again later.');

            $('#loader').hide();
            $('#hotelTable').removeClass('blurred');
        }
    });
    }, 500); 
}



$(document).ready(function() {
    $('table').on('click', '.edit-offer', function(e) {
        e.preventDefault();

        var offerId = $(this).data('offer-id');

        $.ajax({
            url: '/vendor/api/offers/' + offerId + '/',
            type: 'GET',
            success: function(data) {
                $('#offer_id').val(offerId)
                $('#offer_name_edit').val(data.offer_name);
                $('#description_edit').val(data.description);
                $('#discount_percentage_edit').val(data.discount_percentage);
                $('#discount_value_edit').val(data.discount_value);
                $('#minimum_spend_edit').val(data.minimum_spend);
                $('#validity_from_edit').val(data.validity_from);
                $('#promo_validity_from_edit').val(data.validity_from);
                $('#promo_validity_to_edit').val(data.validity_to);
                $('#validity_to_edit').val(data.validity_to);
                $('#promo_code_edit').val(data.promo_code);
                $('#previous_promo_code').val(data.promo_code);
                $('#max_uses_edit').val(data.max_uses);
                $('#targeted_type_edit').val(data.targeted_offer_type);
                $('#occasion_name_edit').val(data.occasion_name);
                $('#points_required_edit').val(data.points_required);
                setCategoryField(data.category);
                
                $('#id02').show(); 
                showRelevantFieldsEdit(data.category);
            },
            error: function(xhr, status, error) {
                console.error('Error fetching offer data:', error);
            }
        });
    });

    const categoryMapping = {
        "common": "Common",
        "promo_code": "Promo Code Specific",
        "targeted_offers": "Targeted Offers",
        "seasonal_event": "Seasonal Event",
        "loyalty_program": "Loyalty Program"
    };

    function setCategoryField(categoryValue) {
        const userFriendlyCategory = categoryMapping[categoryValue] || categoryValue;
        $('#category_edit').val(userFriendlyCategory);
    }

    function getCategoryKey(userFriendlyCategory) {
        return Object.keys(categoryMapping).find(key => categoryMapping[key] === userFriendlyCategory) || userFriendlyCategory;
    }

    function showRelevantFieldsEdit(category) {
        $('#mandotory_edit').hide();
        $('#promo_code_fields_edit').hide();
        $('#common_fields_edit').hide();
        $('#targeted_fields_edit').hide();
        $('#seasonal_event_fields_edit').hide();
        $('#loyalty_program_fields_edit').hide();

        switch (category) {
            case "common":
                $('#mandotory_edit').show();
                $('#common_fields_edit').show();
                break;
            case "promo_code":
                $('#mandotory_edit').show();
                $('#promo_code_fields_edit').show();
                break;
            case "targeted_offers":
                $('#mandotory_edit').show();
                $('#targeted_fields_edit').show();
                break;
            case "seasonal_event":
                $('#mandotory_edit').show();
                $('#seasonal_event_fields_edit').show();
                break;
            case "loyalty_program":
                $('#mandotory_edit').show();
                $('#loyalty_program_fields_edit').show();
                break;
        }
    }

    $('#saveEditedOfferBtn').click(function(e) {
        e.preventDefault();
        var offerId = $('#offer_id').val();

        var userFriendlyCategory = $('#category_edit').val();
        var category = getCategoryKey(userFriendlyCategory);
        var isValid = true;
        $('.error-message_edit').hide(); 

        function showError(element, message) {
            const errorSpan = $(element).closest('.box_container').find('.error-message_edit');
            errorSpan.find('small').text(message).show();
            
            errorSpan.show();
            element.focus();
            isValid = false;
        }
        
        
        const offerName = $("#offer_name_edit");
        const description = $("#description_edit");
        const discountValue = $("#discount_value_edit");
        const discountPercentage = $("#discount_percentage_edit");

        if (!offerName.val().trim()) {
            showError(offerName, "Offer Name is required.");
            return false;
        }
        if (offerName.val().trim().length > 255) {
            showError(offerName, "Offer Name cannot exceed 255 characters.");
            return false;
        }

        if (!description.val().trim()) {
            showError(description, "Description is required.");
            return false;
        }

        if (!discountValue.val().trim() && !discountPercentage.val().trim()) {
            showError(discountPercentage, "You need to enter discount percentage or discount value to proceed");
            return false;
        }


        if (discountValue.val() && discountValue.val() <= 0) {
            showError(discountValue, "Please enter a valid discount percentage.");
            return false;
        } 

        if (discountPercentage.val() && discountPercentage.val() <= 0) {
            showError(discountPercentage, "Please enter a valid discount percentage.");
            return false;
        } 
        
        switch (category) {
            case "common":
                const minimumSpend = $('#minimum_spend_edit');
                const validityFrom = $('#validity_from_edit');
                const validityTo = $('#validity_to_edit');
                console.log("condition check")

                if (!minimumSpend.val()) {
                    showError(minimumSpend, "Minimum spend is required");
                } else if (!/^\d+$/.test(minimumSpend.val())) {
                    showError(minimumSpend, "Minimum spend must be a whole number without decimal points.");
                } else if (parseInt(minimumSpend.val()) <= 0) {
                    showError(minimumSpend, "Please enter a valid minimum spend greater than zero.");
                }
                

                if (!validityFrom.val()) {
                    showError(validityFrom, "Please specify a valid date.");
                }

                if (!validityTo.val()) {
                    showError(validityTo, "Please specify a valid date.");
                }

                const currentDate = new Date();
                currentDate.setHours(0, 0, 0, 0);
                const fromDate = new Date(validityFrom.val());
                fromDate.setHours(0, 0, 0, 0);
                const toDate = new Date(validityTo.val());
                toDate.setHours(0, 0, 0, 0);
                

                if (fromDate < currentDate) {
                    showError(validityFrom, "'Valid From' date cannot be in the past.");
                }
                if (toDate < currentDate) {
                    showError(validityTo, "'Validity To' date cannot be in the past.");
                }
                if (fromDate > toDate) {
                    showError(validityFrom, "Start date cannot be later than end date.");
                }
                break;

            case "promo_code":
                const promoCode = $('#promo_code_edit');
                const maxUses = $('#max_uses_edit');
                const promo_validity_from_edit = document.getElementById("promo_validity_from_edit");
                const promo_validity_to_edit = document.getElementById("promo_validity_to_edit");

                if (!promoCode.val().trim()) {
                    showError(promoCode, "Promo code is required.");
                }

                var previous_promo_code = document.getElementById('previous_promo_code')

                if (previous_promo_code.value !== promoCode.val().trim()){
                    let promoCodeExists = false; 
                    $.ajax({
                        url: '/vendor/promocode_exist/', 
                        method: 'POST',
                        async: false, 
                        data: {
                            promo_code: promoCode.val().trim(),
                            csrfmiddlewaretoken: "{{ csrf_token }}"
                        },
                        success: function(response) {
                            if (response.exists) {
                                promoCodeExists = true;
                                showError(promoCode, "Promo code already exists.");
                            }
                        },
                    });

                    if (promoCodeExists) {
                        return false;
                    }
                }
                

                if (!maxUses.val() || maxUses.val() <= 0) {
                    showError(maxUses, "Please specify a valid number of max uses.");
                }
                if (!promo_validity_from_edit.value) {
                    showError(promo_validity_from_edit, "Please specify a valid date.");
                    return false;
                }

                if (!promo_validity_to_edit.value) {
                    showError(promo_validity_to_edit, "Please specify a valid date.");
                    return false;
                } 
                const promocurrentDateedit = new Date();
                promocurrentDateedit.setHours(0, 0, 0, 0);
                const promofromDateedit = new Date(promo_validity_from_edit.value);
                promofromDateedit.setHours(0, 0, 0, 0);
                const promotoDateedit = new Date(promo_validity_to_edit.value);
                promotoDateedit.setHours(0, 0, 0, 0);
                if (promofromDateedit < promocurrentDateedit) {
                    showError(promo_validity_from_edit, "'Valid From' date cannot be in the past.");
                    return false;
                }
                if (promotoDateedit < promocurrentDateedit) {
                    showError(promo_validity_to_edit, "'Validity To' date cannot be in the past.");
                    return false;
                }

                if (new Date(promo_validity_from_edit.value) > new Date(promo_validity_to_edit.value)) {
                    showError(promo_validity_from_edit, "Start date cannot be later than end date.");
                    return false;
                }
                break;

            case "targeted_offers":
                const targetedType = $('#targeted_type_edit');

                if (!targetedType.val()) {
                    showError(targetedType, "Please select a targeted offer type.");
                }
                break;

            case "seasonal_event":
                const occasionName = $('#occasion_name_edit');

                if (!occasionName.val().trim()) {
                    showError(occasionName, "Occasion name is required.");
                }

                if (!isNaN(occasionName.val().trim())) {
                    showError(occasionName, "Occasion name cannot be a number.");
                }
                break;

            case "loyalty_program":
                const pointsRequired = $('#points_required_edit');

                if (!pointsRequired.val() || pointsRequired.val() <= 0) {
                    showError(pointsRequired, "Please specify the points required.");
                }
                break;
        }

        if (isValid) {
            const offerData = {  
                offer_name: $('#offer_name_edit').val(),
                description: $('#description_edit').val(),
                category: category,
                discount_percentage: $('#discount_percentage_edit').val(),
                discount_value: $('#discount_value_edit').val(),
                minimum_spend: $('#minimum_spend_edit').val(),
                validity_from: $('#validity_from_edit').val(),
                validity_to: $('#validity_to_edit').val(),
                promo_code: $('#promo_code_edit').val(),
                max_uses: $('#max_uses_edit').val(),
                promo_validity_from: $('#promo_validity_from_edit').val(),
                promo_validity_to: $('#promo_validity_to_edit').val(),
                targeted_type: $('#targeted_type_edit').val(),
                occasion_name: $('#occasion_name_edit').val(),
                points_required: $('#points_required_edit').val()
            };

            $.ajax({
                url: '/vendor/api/offers/' + offerId + '/',
                type: 'POST', 
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                data: offerData,
                success: function(data) {
                    $('#id02').hide(); 
                    reload(); 
                },
                error: function(xhr, status, error) {
                    console.error('Error updating offer:', error);
                    alert('Error updating offer. Please try again later.');
                }
            });
        }
    });
});

$(document).ready(function() {
    $('table').on('click', '.delete-offer', function(e)  {
        e.preventDefault();
        
        var offerId = $(this).data('delete-id');
        
        if (confirm('Are you sure you want to delete this offer?')) {
            $.ajax({
                url: '/vendor/api/deleteoffer/' + offerId + '/',
                type: 'DELETE',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                success: function(data) {
                    $(e.target).closest('tr').remove();
                    reload();
                },
                error: function(xhr, status, error) {
                    console.error('Error deleting offer:', error);
                    alert('Error deleting offer. Please try again later.');
                }
            });
        }
    });
});

document.addEventListener('DOMContentLoaded', function() {
    flatpickr("#datePicker", {
        enableTime: false,  
        dateFormat: "Y-m-d"

    });
    flatpickr("#datePicker1", {
        enableTime: false,  
        dateFormat: "Y-m-d"

    });
});

function resetDate(dateId) {
    document.getElementById(dateId).value = '';
}

$(document).ready(function(){
    $('.search_button').click(function(event){
        event.preventDefault();
        $('#loader').show();
        $('#hotelTable').addClass('blurred');

        var loaderTimeout = setTimeout(function() {
            $('#loader').hide();
            $('#hotelTable').removeClass('blurred');
        }, 1000);
        
        var discount = $('.select_discount').val();
        var page = $(this).data('page');
       
        setTimeout(function() {
            $.ajax({
                url:'/vendor/save_offer/filter/',
                type:'POST',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                data:{
                    "discount": discount,
                    "page":page

                },
                success:function(data){
                    $('table thead').html($(data).find('thead').html());
                    $('table tbody').html($(data).find('tbody').html());
                    $('.pagination').html($(data).find('.pagination').html());
                    const rows = $(data).find('table tbody tr');
                    const totalRows = rows.length;

                    // Find the current page number based on the 'current-page' class
                    const currentPage = parseInt($('.current-page').text(), 10) || 1;

                    if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 10)) {
                        $('.pagination').hide();
                    } else {
                        $('.pagination').html($(data).find('.pagination').html()).show();
                    }


                },
                error:function(xhr,status,error){
                    console.error('error :',error);
                }
            });
        }, 500);      
    })    
});
$(document).ready(function () {
$(document).on('click', '.pagination-link', function (e) {
e.preventDefault(); // Prevent default anchor behavior

$('#loader').show();
$('#hotelTable').addClass('blurred');

var discount = $('.select_discount').val();
var page = $(this).data('page');

$.ajax({
    url: '/vendor/save_offer/filter/',
    type: 'GET',
    headers: {
        'X-CSRFToken': window.CSRF_TOKEN
    },
    data: {
        discount: discount,
        page: page
    },
    success: function (data) {
        $('#hotelTable').removeClass('blurred');
        $('#loader').hide();
        $('table thead').html($(data).find('thead').html());
        $('table tbody').html($(data).find('tbody').html());
        $('.pagination').html($(data).find('.pagination').html());
        const rows = $(data).find('table tbody tr');
        const totalRows = rows.length;

        const currentPage = parseInt($('.current-page').text(), 10) || 1;

        if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 10)) {
            $('.pagination').hide();
        } else {
            $('.pagination').html($(data).find('.pagination').html()).show();
        }


    },
    error: function (xhr, status, error) {
        console.error('Error fetching data:', error);
        alert('Error fetching data. Please try again later.');

        $('#loader').hide();
        $('#hotelTable').removeClass('blurred');
    }
});
});
});
function updatePagination(data) {
const rows = $(data).find('table tbody tr');
const totalRows = rows.length;

// Find the current page number based on the 'current-page' class
const currentPage = parseInt($('.current-page').text(), 10) || 1;

if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 10)) {
    $('.pagination').hide();
} else {
    $('.pagination').html($(data).find('.pagination').html()).show();
}

}

$(document).ready(function () {
updatePagination(document);


$.ajax({
url: '/vendor/offer/',
method: 'GET',
success: function (data) {
  $('table tbody').html($(data).find('table tbody').html());
    updatePagination(data);
}
});
});


