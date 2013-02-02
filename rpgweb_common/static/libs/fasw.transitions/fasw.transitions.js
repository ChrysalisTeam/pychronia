/*!
 * FASW Non-jQuery Page Transitions Lightweight v1.3
 * http://fasw.ws/
 *
 * Copyright 2012, Rodrigo Pinto
 * Licensed under the GNU General Public License, version 3 (GPL-3.0)
 * http://www.opensource.org/licenses/GPL-3.0
 * Date: Mon Dec 12 20:00:00 2011 -0400
 * v1.1: 	Modified Firefox compatibility issue. Wed Jan 25 16:30:00 2012 -0400
 * v1.2:	Fixed hyperlink normal functionality when transt attribute is not used
 * 			Fixed Error 0 when running locally
 * 			Fri Feb 3 18:30:00 2012 -0400
 * v1.3:	Back button bug fixed
 * 			iOS compatibility fixed
 * 			Transition Effects for back/forward nav buttons
 * 			Fri March 30 19:10:00 2012 -0400
 * v1.4:	IE9 bug fixed (however transition effect is not shown)
 * 			data-trans attribute instead of trans
 * 			Parameters
 * 			Transitions for buttons
 *			Nested elements inside anchor
 *			CallBack onTransitionFinished
 *			Thu May 31 19:00:00 2012 -0400
 */
function ft(params) {

var ol= document.addEventListener?"DOMContentLoaded":"load"; //on load event
var navB = params.navB || ""; //backbrowser button effect, default empty
var but = params.but || false; //Allow transitions on input type button
var cBa = params.cBa || function() {};

function aDL(url, t, o) {	//Ajax Div Load
	  if (window.XMLHttpRequest) {
	    r = new XMLHttpRequest();
	  } else if (window.ActiveXObject) {
	    r = new ActiveXObject("Microsoft.XMLHTTP");
	  }
	  if (r != undefined) {
	    r.onreadystatechange = function() {Ol(r, t, o);};
	    r.open("GET", url, true);
	    r.send("");
	  }
	}  
function Ol(r, t, o) {	//On load div
	  if (r.readyState == 4) { 
	    if (r.status == 200 || r.status == 0) { 
	    var data = r.responseText;
        var body = data.replace(/^[\S\s]*<body[^>]*?>/i, "").replace(/<\/body[\S\s]*$/i, ""); // extract body, we can't use $() for that
    
        //Optionally, convert the string to a jQuery object:
        //console.log($(body));
    
	      t.innerHTML = body;
	      o();
	    } else {
	      t.innerHTML="Error:\n"+ r.status + "\n" +r.statusText;
	    }
	  }
	}

function DE()		//Div Effect
{
	var dochtml = document.body.innerHTML;
	document.body.innerHTML = "";
	var d1 = document.createElement("div");
	d1.id = "d1";
	d1.style.zIndex = 2;
	d1.style.position = "absolute"; 
	d1.style.width = "100%"; 
	d1.style.height = "100%"; 
	d1.style.left = "0px"; 
	d1.style.top = "0px";
    document.body.appendChild(d1);
    d1.innerHTML = dochtml;
    var d2 = document.createElement("div");
    d2.id = "d2";
    d2.style.zIndex = 1;
    d2.style.position = "absolute"; 
    d2.style.width = "100%"; 
    d2.style.height = "100%"; 
    d2.style.left = "0px"; 
    d2.style.top = "0px";
    document.body.appendChild(d2);
    return {d1: d1, d2: d2 };
}

function timeOuts(e, d1,d2)
{
	setTimeout(function() { d1.className = e + " out"; }, 1);
	setTimeout(function() { d2.className = e + " in"; }, 1);
	setTimeout(function() { 
		document.body.innerHTML = d2.innerHTML;
		cBa();
	}, 706);
}

function slideTo(href, effect, pushstate)
{
	var d = DE();
	var d1 = d.d1;
	var d2 = d.d2;
	aDL(href, d2, 
			function() {
				if (pushstate && window.history.pushState) window.history.pushState("", "", href);
				timeOuts(effect,d1,d2);
			}
	);
}
function dC(e){	//Detect click event
    var o;
    var o=e.srcElement || e.target;
	var tn = o.tagName.toLowerCase();
	if (!but || tn!="input" || o.getAttribute("type")!="button")	//if it is not a button
	{
		//try to find an anchor parent
		while (tn!=="a" && tn!=="body")
		{
			o = o.parentNode;
			tn = o.tagName.toLowerCase();
		}
		if (tn==="body") return;
	}
    var t = o.getAttribute("data-ftrans");
    if (t) 
    {
    	e.preventDefault();
    	var hr = o.getAttribute("href") || o.getAttribute("data-href");
    	if (hr) slideTo(hr, t, true);
    }
}
function aE(ev, el, f) {  //Add event
    if (el.addEventListener)  // W3C DOM
        el.addEventListener(ev,f,false);
    else if (el.attachEvent) { // IE DOM
         var r = el.attachEvent("on"+ev, f);
         return r;
    }
}
aE("click", window, dC);

aE(ol, document, 		//On load
	function(ev)
	{
		aE("popstate", window, function(e) {	//function to reload when back button is clicked
			slideTo(location.pathname, navB, false);
	});
}

);


}