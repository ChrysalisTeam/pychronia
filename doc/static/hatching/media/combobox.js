
/************************************************************************************************************
Editable select
Copyright (C) September 2005  DTHMLGoodies.com, Alf Magne Kalleland

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

Dhtmlgoodies.com., hereby disclaims all copyright interest in this script
written by Alf Magne Kalleland.

Alf Magne Kalleland, 2006
Owner of DHTMLgoodies.com
	
************************************************************************************************************/	


// Path to arrow images
var arrowImage = 'http://the-hatching.prolifik.net/media/images/select_arrow.gif';	// Regular arrow
var arrowImageOver = 'http://the-hatching.prolifik.net/media/images/select_arrow_over.gif';	// Mouse over
var arrowImageDown = 'http://the-hatching.prolifik.net/media/images/select_arrow_down.gif';	// Mouse down


var selectBoxIds = 0;
var currentlyOpenedOptionBox = false;
var editableSelect_activeArrow = false;



function selectBox_switchImageUrl(img, is_hover)
{
	if(is_hover){
		img.src = img.src.replace(arrowImage,arrowImageOver);	
	}else{
		img.src = img.src.replace(arrowImageOver,arrowImage);
	}
	
	
}

function selectBox_showOptions(img, by_button)
{
	if(editableSelect_activeArrow && editableSelect_activeArrow!=img){
		editableSelect_activeArrow.src = arrowImage;
	}
	
	editableSelect_activeArrow = img;
	
	var numId = img.id.replace(/[^\d]/g,'');
	var optionDiv = document.getElementById('selectBoxOptions' + numId);
	
	if(currentlyOpenedOptionBox == optionDiv){
	
		optionDiv.style.display='none';
		if(navigator.userAgent.indexOf('MSIE')>=0)document.getElementById('selectBoxIframe' + numId).style.display='none';
		
		if(by_button){
		  img.src = arrowImageOver;	
		}
		else {
		  img.src = arrowImage;   
		}
	
		currentlyOpenedOptionBox = false;
		
	}else{		
		
		optionDiv.style.display='block';
		if(navigator.userAgent.indexOf('MSIE')>=0)document.getElementById('selectBoxIframe' + numId).style.display='block';
		img.src = arrowImageDown;	
		if(currentlyOpenedOptionBox && currentlyOpenedOptionBox!=optionDiv) currentlyOpenedOptionBox.style.display='none';	
		currentlyOpenedOptionBox = optionDiv;
	
	}
}

function selectOptionValue()
{
	var parentNode = this.parentNode.parentNode;
	var textInput = parentNode.getElementsByTagName('INPUT')[0];
	var newtext = this.innerHTML;
	newtext = newtext.replace("&gt;", ">");
	newtext = newtext.replace("&lt;", "<");
	newtext = newtext.replace("&quot;", '"');
	//alert(newtext);
	textInput.value = newtext;	
	this.parentNode.style.display='none';	
	
	document.getElementById('arrowSelectBox' + parentNode.id.replace(/[^\d]/g,'')).src = arrowImage;
	
	if(navigator.userAgent.indexOf('MSIE')>=0){
	   document.getElementById('selectBoxIframe' + parentNode.id.replace(/[^\d]/g,'')).style.display='none';}
	
}
var activeOption;
function highlightSelectBoxOption()
{
    
	if(this.style.backgroundColor=='#316AC5'){
		this.style.backgroundColor='';
		this.style.color='';
	}else{
		this.style.backgroundColor='#316AC5';
		this.style.color='#FFF';			
	}	
	
	if(activeOption){
		activeOption.style.backgroundColor='';
		activeOption.style.color='';			
	}
	activeOption = this;
	
}

function createEditableSelect(dest)
{

	dest.className='selectBoxInput';		
	var div = document.createElement('DIV');
	div.style.styleFloat = 'left';
	div.style.width = dest.offsetWidth + 16 + 'px';
	div.style.position = 'relative';
	div.id = 'selectBox' + selectBoxIds;
	var parent = dest.parentNode;
	parent.insertBefore(div,dest);
	div.appendChild(dest);	
	div.className='selectBox';
	div.style.zIndex = 10000 - selectBoxIds;
	div.style.margin = "0 auto";

	var img = document.createElement('IMG');
	img.src = arrowImage;
	img.className = 'selectBoxArrow';
	
	img.onmouseover = function() {selectBox_switchImageUrl(img, true);};
	img.onmouseout = function() {selectBox_switchImageUrl(img, false);};
	img.onclick = function() {selectBox_showOptions(img, true);};
	img.id = 'arrowSelectBox' + selectBoxIds;

	div.appendChild(img);
	
	var optionDiv = document.createElement('DIV');
	optionDiv.id = 'selectBoxOptions' + selectBoxIds;
	optionDiv.className='selectBoxOptionContainer';
	optionDiv.style.width = div.offsetWidth + -5 + 'px';
	optionDiv.style.margin = 0;
	
    // Hide the modal dialog when someone clicks outside of it.
    
    $(optionDiv).bind("clickoutside", function(event){
        if (currentlyOpenedOptionBox == optionDiv && event.target != img){  
            selectBox_showOptions(img, false);
        }
    });
    
    div.appendChild(optionDiv);
	
	if(navigator.userAgent.indexOf('MSIE')>=0){
		var iframe = document.createElement('<IFRAME src="about:blank" frameborder=0>');
		iframe.style.width = optionDiv.style.width;
		iframe.style.height = optionDiv.offsetHeight + 'px';
		iframe.style.display='none';
		iframe.id = 'selectBoxIframe' + selectBoxIds;
		div.appendChild(iframe);
	}
	
	if(dest.getAttribute('selectBoxOptions')){
		var options = dest.getAttribute('selectBoxOptions').split('|');
		var optionsTotalHeight = 0;
		var optionArray = new Array();
		for(var no=0;no<options.length;no++){
			var anOption = document.createElement('DIV');
			//alert(options[no]);
			anOption.innerHTML = options[no];
			anOption.className='selectBoxAnOption';
			anOption.style.margin = '0';
			anOption.onclick = selectOptionValue;
			anOption.style.width = optionDiv.style.width.replace('px','') - 22 + 'px'; 
			anOption.onmouseover = highlightSelectBoxOption;
			optionDiv.appendChild(anOption);	
			optionsTotalHeight = optionsTotalHeight + anOption.offsetHeight;
			optionArray.push(anOption);
		}
		if(optionsTotalHeight > optionDiv.offsetHeight){				
			for(var no=0;no<optionArray.length;no++){
				optionArray[no].style.width = optionDiv.style.width.replace('px','') - 22 + 'px'; 	
			}	
		}		
		optionDiv.style.display='none';
		optionDiv.style.visibility='visible';
	}
	
	selectBoxIds = selectBoxIds + 1;
}	



function initializeScripts()
{

	var inputsCollection = document.getElementsByTagName("input");
	for(var i=0;i<inputsCollection.length;i++)
	{	
	
		if(inputsCollection[i].type == "text" && inputsCollection[i].getAttribute('selectBoxOptions'))
		{
			//alert(inputsCollection[i].getAttribute('selectBoxOptions'));
			createEditableSelect(inputsCollection[i]);
		}
		
	   // alert(inputsCollection[i].name);
	}

}


var alreadyrunflag=0 //flag to indicate whether target function has already been run

if (document.addEventListener)
  document.addEventListener("DOMContentLoaded", function(){alreadyrunflag=1; initializeScripts()}, false)
else if (document.all && !window.opera){
  document.write('<script type="text/javascript" id="contentloadtag" defer="defer" src="javascript:void(0)"><\/script>')
  var contentloadtag=document.getElementById("contentloadtag")
  contentloadtag.onreadystatechange=function(){
    if (this.readyState=="complete"){
      alreadyrunflag=1
      initializeScripts()
    }
  }
}

window.onload=function(){
  setTimeout("if (!alreadyrunflag) initializeScripts();", 0)
}
