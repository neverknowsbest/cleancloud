function load_page_onclick(page) {
	window.location = page;
}

function back() {
	window.history.back();
}

function hide_all() {
	$(".row-details").hide();
	var all_toggles = $("label[id*=toggle]");
	var current_toggles = all_toggles.html();	
	if (current_toggles != undefined) {
		all_toggles.html(current_toggles.replace("minus", "plus"));		
	}
}

function expand_all() {
	$(".row-details").show();
	var all_toggles = $("label[id*=toggle]");
	var current_toggles = all_toggles.html();	
	all_toggles.html(current_toggles.replace("plus", "minus"));
}

function display_details(id) {
	$("tr[id*=details-" + id + "-]").toggle(500);
	var current_toggle = $("#toggle" + id).html();
	if (current_toggle.indexOf("plus") != -1) {
		$("#toggle" + id).html(current_toggle.replace("plus", "minus"));
	} else {
		$("#toggle" + id).html(current_toggle.replace("minus", "plus"));
	}
}

//AJAX method to send edited changes to the server in the background
function save_edits_ajax(jobid, row_id, save_data) {
	var csrftoken = getCookie('csrftoken');
	$.ajaxSetup({
	    crossDomain: false, // obviates need for sameOrigin test
	    beforeSend: function(xhr, settings) {
	        if (!csrfSafeMethod(settings.type)) {
	            xhr.setRequestHeader("X-CSRFToken", csrftoken);
	        }
	    }
	});	
	
	$.ajax({
			type : 'POST',
			url  : '/edit/' + jobid + '/',
			async : true,
			cache : false,
			data : save_data,
			dataType : "html",
			success : function(response, status, jqxhr) {
				$('#editstatus' + row_id).hide().html(response).fadeIn(1000);
				$('#editstatus' + row_id).hide().html(response).fadeOut(5000);
			},
			error : function(XMLHttpRequest, textstatus, error) { 
				$('#editstatus' + row_id).hide().html(error).fadeIn();
			}
	});
}

/**
Use AJAX to save the contents of the input box with the given id back to the result database. If no id is specified, save ALL input boxes. 

Called when "save" button is clicked or enter key is pressed in editing box.
*/
function save_results_changes(jobid, id, data) {
	var row_id = id.split('-')[0];
	
	//If no id is specified, save ALL input boxes
	if (id == undefined) {
		var save_data = $('input[id*="edit"]').serialize();
	} else {
		var save_data = $('#edit' + id).serialize();
	}
	
	//If data is provided, use that instead of input box input
	if (data != undefined) {
		var json = {};
		json[id] = data;
		var save_data = json;
	}
	
	save_edits_ajax(jobid, row_id, save_data);
	
	//Function to revert input box to plaintext
	var input_to_plaintext = function() {
		if (id != undefined) {
			if (data != undefined) {
				var input_data = data;
			} else {
				var input_data = $('#edit' + id).val();
			}
			var onclick = "send_value_to_input('" + jobid + "', '" + id + "', '" + input_data + "')";
			$('#cell' + id).html(input_data);
			$('#cell' + id).attr('onclick', onclick);
			}
		};
		
	//Delay reverting input box for a short while so the table cell doesn't pick up the mouse click from clicking the save button
	setTimeout(input_to_plaintext, 250);	
}

/**
Sends the value of the clicked table cell to a new input box, which will appear in the current cell.
*/
function send_value_to_input(jobid, input_id, value) {
	//HTML for the input box that will replace the contents of the current cell
	var edit_row = "<span class='input-append'><input id='edit" + input_id + "' type='text' value='" + value + "' name='" + input_id + "' class=\"inline\"/><button id='editsave" + input_id + "' class='btn btn-success' title='Save Changes' onclick='save_results_changes(\"" + jobid + "\", \"" + input_id + "\")'><i class=\"icon-ok\"></i></button><button class='btn btn-danger' title='Revert to Original' onclick='revert(\"" + jobid + "\", \"" + input_id + "\")'><i class=\"icon-repeat\"></i></button></span>";
	
	//Change the table cell that was clicked into an input box
	$('td[id="cell' + input_id + '"]').html(edit_row);
	$('td[id="cell' + input_id + '"]').attr('onclick', '');	
	
	//Catch enter keypress, save input data to server when user hits enter
	$('#edit' + input_id).keyup(function(event){
		if(event.which == 13) {
			save_results_changes(jobid, input_id);
		}
	});
}

/**
Revert the contents of a table cell back to the original data, which is downloaded in the background
*/
function revert(jobid, input_id) {	
	// AJAX method to get original row data in the background
	$.ajax({
			type : 'GET',
			url  : '/revert/' + jobid + '/' + input_id + '/',
			async : true,
			cache : false,
			dataType : "json",
			success : function(json) {
				var onclick = "send_value_to_input('" + jobid + "', '" + input_id + "', '" + json['original'] + "')";
				$('#cell' + input_id).html(json['original']);
				$('#cell' + input_id).attr('value', json['original']);				
				$('#cell' + input_id).attr('onclick', onclick);
				
				//Save changes back to database
				setTimeout(function(){save_results_changes(jobid, input_id, json['original']);}, 250);
			},
			error : function(XMLHttpRequest, textstatus, error) { 
				alert(error);
			}
	});
}

/**
FROM DJANGO https://docs.djangoproject.com/en/dev/ref/contrib/csrf/#ajax 
*/
function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

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
/* END FROM DJANGO */

/**
Main AJAX function for status page. This checks the job status and updates the page with the status, as well as filling in the results when they're available.
*/
function comet(jobid, delay) {
	if (delay == "undefined") {
		delay = 20000;
	}
	var csrftoken = getCookie('csrftoken');
	$.ajaxSetup({
	    crossDomain: false, // obviates need for sameOrigin test
	    beforeSend: function(xhr, settings) {
	        if (!csrfSafeMethod(settings.type)) {
	            xhr.setRequestHeader("X-CSRFToken", csrftoken);
	        }
	    }
	});

	$('#status').html("Getting status from server...");
	if ($('#tracker_url').attr('href') == "") {
		$('#tracker_span').hide();		
	}
	
	var ajax_func = function() {
		$.ajax({
			type : 'Get',
			url  : '/check/' + jobid + '/',
			async : true,
			cache : false,
			dataType : "json",
			success : function(json) {
				if(json == null){
					$('#status').html('No response from server.');
					var com = function(){comet(jobid);};
					setTimeout(com, delay);
				} else { 
					progress = parseInt(json['progress']);
					
					$('#status').html(json['status']);
					$('#details').html(json['emr_details']);
					
					if (json['emr_tracker'] != "") {
						$('#tracker_url').attr('href', json['emr_tracker']);
						$('#tracker_span').show();
					}

					if (5.7 * progress > $('.bar').width()) {
						$('.bar').width(progress * 5.7);
						$('.bar').text(progress + "%");
					}
				
					if (json['status'] == "COMPLETED" || 
						json['status'] == "Testing OK") {
							window.location.replace(json['redirect'])
						// display_results(json);
					} else if (json['status'] == "FAILED") {
						$('#results').html(json['results']);
					} else if ((json['status'] == "WAITING" || 
								json['status'] == "TERMINATED") && 
								json['results'].length > 0) {
						window.location.replace(json['redirect'])
						// display_results(json);
					} else if (json['status'] == "CANCELLED") {
					} else {
						$("#cancel").html("<input class='btn btn-large btn-primary span3' onclick=\"cancel('" + jobid + "')\" value='Cancel Running Job'>");
						var com = function(){comet(jobid);};
						setTimeout(com, delay);
					}
				}
			},
			error : function(XMLHttpRequest, textstatus, error) { 
				$('#status').html(error);
				var com = function(){comet(jobid);};
				setTimeout(com, delay);
			}
		});};
	
	if (jobid != undefined) {
		setTimeout(ajax_func, delay); // delay first status check by 1 second
	}
}

/**
Fills in the result table when it is available from the AJAX status check.
*/
function display_results(json) {
	//Tablesorter sorting
	var sorting = [[2,0]]; 
	
	//Set status bar to 100%
	$('.bar').width(570);
	$('.bar').text(100 + "%");
	
	//Fill in the results div with the results table
	$('#results').html(json['results']);

	//Hide secondary rows by default
	$(".row-details").hide();
	
	//Enable tablesorter, sort by default tablesort options in sorting
	$("#result_table").tablesorter();
	$("#result_table").trigger("update"); 
	$("#result_table").trigger("sorton",[sorting]);	
}

//Cancel job
function cancel(jobid) {
	if (base_url == undefined) {
		var base_url = ".";
	}
	$("#status").html("Cancelling...");
	$.ajax({
		type	: 'Get',
		url		: '/cancel/' + jobid + '/',
		async	: true,
		cache	: false
	});
	$("#cancel").hide(500);
	$("#progress").hide(500);
}

/**
Toggles the remove row buttons from active to inactive state, according to the given state
*/
function toggle_remove_row_button(jobid, rowid) {
	//Locate the OK/remove buttons via jQuery
	var ok_button = $('#button_ok_' + rowid);
	var remove_button = $('#button_remove_' + rowid);
	
	//Get the current CSS classes of the buttons
	var ok_button_class = ok_button.attr('class');
	var remove_button_class = remove_button.attr('class');
	
	//if OK button is active
	if (ok_button_class.indexOf("active") != -1) {
		//Toggle OK button to inactive
		ok_button.attr('class', ok_button_class.replace("active", ""));
		remove_button.attr('class', remove_button_class + " active");

		//Save OK button state on server
		var save_data = {};
		save_data[rowid] = 0;
		save_edits_ajax(jobid, rowid, save_data);
		
		//Remove this row from the list of rows to delete
		var rows_to_delete = $('#delete').attr('value');
		$('#delete').attr('value', rows_to_delete.replace(']', ", " + rowid + "]"));		
	} else { //Remove button is active
		//Toggle OK button to active
		remove_button.attr('class', remove_button_class.replace("active", ""));
		ok_button.attr('class', ok_button_class + " active");
		
		//Save OK button state on server
		var save_data = {};
		save_data[rowid] = 1;
		save_edits_ajax(jobid, rowid, save_data);
		
		//Add this row to the list of rows to delete
		var rows_to_delete = $('#delete').attr('value');
		$('#delete').attr('value', rows_to_delete.replace(', ' + rowid, '').replace('[' + rowid + ', ', ''));
	}
}

/* Highlight active page in navbar */
function highlight_active_nav() {
	var path = window.location.pathname;
	var nav_tag;
	if (path.indexOf("profile") >= 0) {
		nav_tag = $("#nav-profile");
	} else if (path.indexOf("files") >= 0) {
		nav_tag = $("#nav-files");
	} else if (path.indexOf("functions") >= 0) {
		nav_tag = $("#nav-functions");
	} else if (path.indexOf("job_history") >= 0) {
		nav_tag = $("#nav-jobs");
	} else {
		return;
	}
	nav_tag.attr("class", "active");
}

/* Remove a file from a user's library */
function remove_file(file_id) {
	$.ajax({
		type	: 'Get',
		url		: '/remove/' + file_id + '/',
		async	: true,
		cache	: false,
		success : function(json) {
			$("#" + file_id).hide(500);
		}
	});	
}

/* Cancel an active job from the job history page */
function cancel_job(job_id) {
	$.ajax({
		type	: 'Get',
		url		: '/cancel/' + job_id + '/',
		async	: true,
		cache	: false,
		success : function(json) {
			$("#" + job_id).hide(500);
		}
	});	
}

/* Hide inactive job from the job history page */
function hide_job(job_id) {
	$.ajax({
		type	: 'Get',
		url		: '/hide/' + job_id + '/',
		async	: true,
		cache	: false,
		success : function(json) {
			$("#" + job_id).hide(500);
		}
	});	
}