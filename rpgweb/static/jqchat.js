// Chat client code.


// Keep track of the last message received (to avoid receiving the same message several times).
// This global variable is updated every time a new message is received.
var slice_index = 0;

// URL to contact to get updates.
var url = null;

// How often to call updates (in milliseconds)
var CallInterval = 3000;

// Max delay of an ajax request attempt
// Another ajax request might be sent in the meantime, 
// but it's not a problem thanks to request flags below
var ajax_timeout_ms = 6000;

// ID of the function called at regular intervals.
var IntervalID = 0;
// to clear it : clearInterval(IntervalID);
// also possible : setTimeout('callServer();', CallInterval);

// A callback function to be called to further process each response.
var prCallback = null;

// to prevent redundant chat updates
var get_request_in_progress = false;
var post_request_in_progress = false;

function callServer(){

	// At each call to the server we pass data.
	if (get_request_in_progress) return;
	
	get_request_in_progress = true;
	
    $.ajax({
          url: url,
          type: "GET",
          data: {slice_index: slice_index},
          dataType: "json",
          timeout: ajax_timeout_ms, // in ms
          success: processResponse,
          error: function(){
                            $("#errordiv").css("visibility", "visible");
                           },
          complete: function(){ get_request_in_progress = false; } // always called
          });
}


function processResponse(payload) {

    //if (!payload) return; // may only happen in buggy jquery 1.4.2
    
    $("#errordiv").css("visibility", "hidden");
    
	// Get the slice index, store it in global variable to be passed to the server on next call.
	slice_index = payload.slice_index;
	
	for(id in payload.messages) {
	    if(payload.messages[id]["message"]) {
	        var span = document.createElement("span")
	        span.style.color = payload.messages[id]["color"]
	        span.innerHTML = payload.messages[id]["message"]
	         $("#chatwindow").append(span);
	         $("#chatwindow").append("<br/>");
	    }
	}
	// Scroll down if messages fill up the div.
	var objDiv = document.getElementById("chatwindow");
	objDiv.scrollTop = objDiv.scrollHeight;

	// Handle custom data (data other than messages).
	// This is only called if a callback function has been specified.
	if(prCallback != null) prCallback(payload);
}



function InitChatWindow(ChatMessagesUrl, CanChat, ProcessResponseCallback){
    /**   The args to provide are:
	- the URL to call for AJAX calls.
	- A callback function that handles any data in the JSON payload other than the basic messages.
	  For example, it is used in the example below to handle changes to the room's description. */

	$("#loading").remove(); // Remove the dummy 'loading' message.

	// Push the calling args into global variables so that they can be accessed from any function.
	url = ChatMessagesUrl;
	prCallback = ProcessResponseCallback;

    // The below will trigger the first call only after X milliseconds; so we
    // manually trigger an immediate call.
    callServer();

	// Read new messages from the server every X milliseconds.
	IntervalID = setInterval(callServer, CallInterval);

    
    if (CanChat){
    	// Process messages input by the user & send them to the server.
    	$("form#chatform").submit(function(){
    	
    	   if (post_request_in_progress) return false;
    
    		// If user clicks to send a message on a empty message box, then don't do anything.
    		msg = $.trim($("#msg").val())
    		if(msg == "") return false;
    		
    		post_request_in_progress = true;
    		 
            $.ajax({
              url: url,
              type: "POST",
              data: {message: msg},
              timeout: ajax_timeout_ms, // in ms
              success: function(payload){ 
                                        //if (!payload) return; // may only happen in buggy jquery 1.4.2
                                        $("#msg").val(""); // clean out contents of input field.
                                        $("#errordiv").css("visibility", "hidden");
                                        },
              error: function(){ $("#errordiv").css("visibility", "visible"); },
              complete: function(){ post_request_in_progress = false; // always called
                                    callServer(); } 
              });
        
    
            /** unsafe
    		$.post(url,
    				{
    				    message: msg
               		},
               		function(){
             						     $("#msg").val(""); // clean out contents of input field.
           							 }
           	);*/
           	
    		return false;
    	});
    }

} // End InitChatWindow





/**	This code below is an example of how to extend the chat system.
 * It's used in the second example chat window and allows us to manage a user-updatable
 * description field.
 *  */

// Callback function, processes extra data sent in server responses.
function HandleChattersList(payload) {
	//$("#chatroom_description").text(payload.users);
}
