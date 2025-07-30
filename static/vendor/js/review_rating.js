        const hotel_id=document.getElementById('selected_hotel').value
        function showCustomAlert(alertId) {
            document.querySelectorAll('.alert-message').forEach(msg => msg.style.display = 'none'); 
            document.getElementById(alertId).style.display = 'block'; 
            document.getElementById("customAlertModal").style.display = "flex";
        }   
        // Script to open and close sidebar
        const errorMessage = document.getElementById("error-message");
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
                var page = $(this).data('page');

                console.log(review_rating);
                setTimeout(function() {
                    $.ajax({
                        url: `/vendor/review/?hotel_id=${hotel_id}`,
                        type: 'POST',
                        headers: {
                            'X-CSRFToken': window.CSRF_TOKEN
                        },
                        data: {
                            from_date: fromDate,
                            to_date: toDate,
                            review_rating:review_rating,
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
                                }
                        },
                        error: function(xhr, status, error) {
                            console.error('Error Fetching Refund and cancellation details:', error);
                            showCustomAlert("error-fetch-reviews");                        }
                    });
                }, 500);
            });
        });

        $(document).on('click', '.pagination-link', function (e) {
            e.preventDefault();

            // Show loader and apply blur effect
            $('.loader-container').css('display', 'flex');
            $('#hotelTable').addClass('blurred');

            var loaderTimeout = setTimeout(function () {
                $('.loader-container').hide();
                $('#hotelTable').removeClass('blurred');
            }, 8000);

            var page = $(this).data('page'); // Get the page number
            var fromDate = $('.from_date').val();
            var toDate = $('.to_date').val();
            var review_rating = $('#review_rating').val();

            console.log(review_rating);

            setTimeout(function () {
                $.ajax({
                    url: `/vendor/review/?hotel_id=${hotel_id}`,
                    type: 'POST',
                    headers: {
                        'X-CSRFToken': window.CSRF_TOKEN
                    },
                    data: {
                        from_date: fromDate,
                        to_date: toDate,
                        review_rating: review_rating,
                        page: page
                    },
                    success: function (data) {
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

                            // Update pagination visibility
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
                    error: function (xhr, status, error) {
                        clearTimeout(loaderTimeout);
                        $('.loader-container').hide();
                        $('#hotelTable').removeClass('blurred');
                        console.error('Error Fetching Review and Rating details:', error);
                        showCustomAlert("error-fetch-reviews");
                    }
                });
            }, 500);
        });

        // $(document).ready(function() {
        //     $('.respond_button').click(function(event) {
        //         event.preventDefault();
                
        //         var id = $(this).data('review-id')
        //         var formActionUrl = '/vendor/review/respond/' + id +'/';
        //         console.log(id,formActionUrl);
        //         $('#responseForm').attr('action', formActionUrl);
        //     });
        // });
            function updatePagination(data) {
            const rows = $(data).find('table tbody tr');
            const totalRows = rows.length;

            const currentPage = parseInt($('.current-page').text(), 15) || 1;

            if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 15)) {
                $('.pagination').hide();
            } else {
                $('.pagination').html($(data).find('.pagination').html()).show();
            }

    }

        $(document).ready(function () {
            updatePagination(document);

        
            $.ajax({
                url: `/vendor/review/?hotel_id=${hotel_id}`,
                method: 'GET',
                success: function (data) {
                $('table tbody').html($(data).find('table tbody').html());
                    updatePagination(data);
                }
            });
        });
    function reload() {
        var fromDate = $('.from_date').val();
        var toDate = $('.to_date').val();
        var review_rating = $('#review_rating').val();
        var page =  parseInt($('.current-page').text(), 10) || 1;
        $('.loader-container').css('display', 'flex');
        $('#hotelTable').addClass('blurred');

        var loaderTimeout = setTimeout(function () {
            $('.loader-container').hide();
            $('#hotelTable').removeClass('blurred');
        }, 8000);
    
        setTimeout(function() {
            $.ajax({
                url: `/vendor/review/?hotel_id=${hotel_id}`,
                type: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN
            },
            data: {
                from_date: fromDate,
                to_date: toDate,
                review_rating: review_rating,
                page: page
            },
            success: function (data) {
                $('#hotelTable').removeClass('blurred');
                $('.loader-container').hide();
                $('table thead').html($(data).find('thead').html());
                $('table tbody').html($(data).find('tbody').html());
                $('.pagination').html($(data).find('.pagination').html());
                const rows = $(data).find('table tbody tr');
                const totalRows = rows.length;

                // Find the current page number based on the 'current-page' class
                const currentPage = parseInt($('.current-page').text(), 15) || 1;

                if ((totalRows === 1 && rows.find('td[colspan]').length > 0) || (currentPage === 1 && totalRows < 15)) {
                    $('.pagination').hide();
                } else {
                    $('.pagination').html($(data).find('.pagination').html()).show();
                }
            },
            error: function (xhr, status, error) {
                console.error('Error fetching data:', error);
                showCustomAlert("error-pagination");

                $('.loader-container').hide();
                $('#hotelTable').removeClass('blurred');
            }
        });
    }, 500); 
}
    function resetErrors(modalId) {
        $(modalId).find('.error-message').hide();
    }  
    $(document).ready(function () {
    $(document).on('click', '.respond_button', function (e) {
        e.preventDefault(); 
        resetErrors('#id02');

        const reviewId = $(this).data('review-id'); 
        $('#reviewId').val(reviewId); 
        $('#id02').css('display', 'flex'); 
        console.log( reviewId)
    });

    $('#responseForm').on('submit', function (e) {
        e.preventDefault(); 

        const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
        const reviewId = $('#reviewId').val(); 
        const respondText = $('#respond').val(); 
        console.log(respondText)
        console.log(reviewId)

        const errorMessageEmpty = $('#error-message-empty');
        const errorMessageLength = $('#error-message-length');
        errorMessageEmpty.hide();
        errorMessageLength.hide();

        if (!respondText.trim()) {
            errorMessageEmpty.show();
            return;
        }
        if ((respondText.length > 250) || (respondText.length < 5)) {
            errorMessageLength.show();
            return;
        }

        $.ajax({
            url: `/vendor/review/respond/${reviewId}/?hotel_id=${hotel_id}`, 
            type: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
            },
            data: {
                respond: respondText,
            },
            success: function (response) {
                
                $('#id02').hide(); 
                reload(); 
                showCustomAlert("response-success");

            },
            error: function (xhr, status, error) {
                console.error("Error:", error);
                showCustomAlert("error-submit-response");
            },
        });
    });

});



    $(document).ready(function () {
        $(document).on('click', '.edit-review', function (e) {
            e.preventDefault();
            const reviewId = $(this).data("review-id");

            $.ajax({
                url: `/vendor/review/edit/${reviewId}/?hotel_id=${hotel_id}`, 
                type: "GET",
                success: function (response) {
                    $("#id03").css("display", "flex");

                    $("#respond-message").val(response.review_text);

                    $("#reviewId").val(reviewId);
                },
                error: function (xhr, status, error) {
                    console.error("Failed to fetch review:", error);
                    showCustomAlert("error-fetch-reviews");
                },
            });
        });

        $('#editresponseForm').click(function(e) {
            e.preventDefault();
            resetErrors('#id03');
            const csrfToken = $("input[name=csrfmiddlewaretoken]").val();
            const reviewId = $('#reviewId').val(); 
            const respondText = $('#respond-message').val(); 
        

            const errorMessageEmpty = $('#edit-error-message-empty');
            const errorMessageLength = $('#edit-error-message-length');

            if (!respondText.trim()) {
                errorMessageEmpty.show();
                return;
            }
            if ((respondText.length > 250) || (respondText.length < 5)) {
                errorMessageLength.show();
                return;
            }
            $.ajax({
                url: `/vendor/review/edit/${reviewId}/?hotel_id=${hotel_id}`, 
                type: "POST",
                headers: {
                'X-CSRFToken': csrfToken,
               },
                data: {
                respond: respondText,
        
                },                
                success: function (response) {
                    $("#id03").hide();
                    reload(); 
                    showCustomAlert("response-success");
                },
                error: function (xhr, status, error) {
                    console.error("Failed to post response:", error);
                    showCustomAlert("error-submit-response");
                },
            });
        });
    });
    $(document).ready(function () {
        $('table').on('click', '.delete-review', function (e) {
            e.preventDefault();
    
            const reviewId = $(this).data("review-id");
    
            $("#confirmDeleteModal").css("display","flex");
    
            $("#confirmDeleteModal .confirm-ok").off("click").on("click", function () {
                $("#confirmDeleteModal").hide();
                deleteReview(reviewId);
            });
    
            $("#confirmDeleteModal .confirm-cancel").off("click").on("click", function () {
                $("#confirmDeleteModal").hide();
            });
        });
    
        function deleteReview(reviewId) {
            $.ajax({
                url: `/vendor/review/edit/${reviewId}/?hotel_id=${hotel_id}`,
                type: 'DELETE',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN
                },
                success: function (data) {
                    reload();
                    showCustomAlert("delete-success");
                },
                error: function (xhr, status, error) {
                    console.error('Error deleting response:', error);
                    showCustomAlert("error-delete-response");
                }
            });
        }
    });
    

