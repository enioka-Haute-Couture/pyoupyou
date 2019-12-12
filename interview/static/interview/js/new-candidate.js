function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            // Only send the token to relative URLs i.e. locally.
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});

$('#create-source ').on('submit', function(event){
    event.preventDefault();
    $.ajax({
        url : "/create_source/",
        type : "POST",
        data : { 'source-name': $('#id_source-name').val(), 'source-category': $('#id_source-category').val() },
        success : function(json) {
            $('#id_source-name').val('');
            $('#id_source-category').val('');
            $('#create-source').modal('hide')
        },

        error : function(xhr,errmsg,err) {
//TODO
        }
    });
    return false;
});

$('#create-offer ').on('submit', function(event){
    event.preventDefault();
    $.ajax({
        url : "/create_offer/",
        type : "POST",
        data : { 'offer-name': $('#id_offer-name').val(), 'offer-subsidiary': $('#id_offer-subsidiary').val() },
        success : function(json) {
            $('#id_offer-name').val('');
            $('#id_offer-subsidiary').val('');
            $('#create-offer').modal('hide')
        },

        error : function(xhr,errmsg,err) {
//TODO
        }
    });
    return false;
});
