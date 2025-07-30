// Script to open and close sidebar
function w3_open() {
document.getElementById("mySidebar").style.display = "block";
document.getElementById("myOverlay").style.display = "block";
}


function w3_close() {
document.getElementById("mySidebar").style.display = "none";
document.getElementById("myOverlay").style.display = "none";
}

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
$(document).ready(function() {
    $('#review_search').click(function() {

        $('.loader-container').css('display', 'flex');
        $('#hotelTable').addClass('blurred');

        var loaderTimeout = setTimeout(function() {
            $('.loader-container').hide();
            $('#hotelTable').removeClass('blurred');
        }, 8000);
        
        var fromDate = $('.from_date').val();
        var toDate = $('.to_date').val();
        var review_rating = $('#review_rating').val();
        var category = $('#category').val();
        var page = $(this).data('page');
        console.log(review_rating);
        setTimeout(function() {
            $.ajax({
                url: '/super_user/review&rating/',
                type: 'POST',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                data: {
                    from_date: fromDate,
                    to_date: toDate,
                    review_rating:review_rating,
                    category:category,
                    page: page, 
                },
                success: function(data) {
                    // $('table tbody').html($(data).find('table tbody').html());
                    clearTimeout(loaderTimeout);

            $('.loader-container').hide();
            $('#hotelTable').removeClass('blurred');

            var tableContent = $(data).find('table tbody').html();
            if ($.trim(tableContent).length > 0) {
                $('table tbody').html(tableContent);
                $('.no_data_found').hide();
                const rows = $(data).find('table tbody tr');
                const totalRows = rows.length;

                const currentPage = parseInt($(data).find('.current-page').text(), 15) || 1;

                if (currentPage === 1 && totalRows < 15) {
                    $('.pagination').hide();
                } else {
                    $('.pagination').html($(data).find('.pagination').html()).show();
                }  
            } else {
                    $('table tbody').html('<tr><td colspan="5" style="text-align: center;">No data found</td></tr>');
                    $('.pagination').hide();
                }
                },
                error: function(xhr, status, error) {
                    console.error('Error in Fetching reveiw details:', error);
                    alert('Error in Fetching reveiw details. Please try again later.');
                    $('.pagination').hide();
                }
            });
        }, 500);
    });
});
function openModal(element) {
    const reviewText = element.nextElementSibling.textContent;
    document.getElementById('newModalContent').textContent = reviewText;
    document.getElementById('main-modal').style.display = 'flex';
}
function closeModal() {
document.getElementById('main-modal').style.display = 'none';
}


    $(document).on('click', '.pagination-link', function (e) {
    e.preventDefault();

    $('.loader-container').css('display', 'flex');
    $('#hotelTable').addClass('blurred');

    var loaderTimeout = setTimeout(function() {
        $('.loader-container').hide();
        $('#hotelTable').removeClass('blurred');
        alert('Request timed out. Please try again.');
    }, 8000);

    var fromDate = $('.from_date').val();
    var toDate = $('.to_date').val();
    var review_rating = $('#review_rating').val();
    var category = $('#category').val();
    var page = $(this).data('page'); // Get page number from clicked link

    $.ajax({
        url: '/super_user/review&rating/',
        type: 'POST',
        headers: {
            'X-CSRFToken': window.CSRF_TOKEN,
        },
        data: {
            from_date: fromDate,
            to_date: toDate,
            review_rating: review_rating,
            category: category,
            page: page, 
        },
        success: function(data) {
            clearTimeout(loaderTimeout);

            $('.loader-container').hide();
            $('#hotelTable').removeClass('blurred');

            var tableContent = $(data).find('table tbody').html();
            if ($.trim(tableContent).length > 0) {
                $('table tbody').html(tableContent);
                $('.no_data_found').hide();
                const rows = $(data).find('table tbody tr');
                const totalRows = rows.length;

                const currentPage = parseInt($(data).find('.current-page').text(), 15) || 1;

                if (currentPage === 1 && totalRows < 15) {
                    $('.pagination').hide();
                } else {
                    $('.pagination').html($(data).find('.pagination').html()).show();
                }  
            } else {
                    $('table tbody').html('<tr><td colspan="5" style="text-align: center;">No data found</td></tr>');
                    $('.pagination').hide();
                }
        },
        error: function(xhr, status, error) {
            console.error('Error in Fetching review details:', error);
            alert('Error in Fetching review details. Please try again later.');
            $('.pagination').hide();
        }
    });
});
function updatePagination(data) {
    const rows = $(data).find('table tbody tr');
    const totalRows = rows.length;

    const currentPage = parseInt($('.current-page').text(), 15) || 1;

    if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 15)) {
        $('.pagination').hide();
    } else {
        $('.pagination').html($(data).find('.pagination').html()).show();
    }         l_table_list
}

$(document).ready(function () {
    updatePagination(document);

    $.ajax({
        url: '/super_user/review&rating/',
        method: 'GET',
        success: function (data) {
            $('table tbody').html($(data).find('table tbody').html());
            updatePagination(data);
        }
    });
});


