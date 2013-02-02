
FASW Non-jQuery Page Transitions Lightweight v1.4
http://fasw.ws/

Copyright 2012, Rodrigo Pinto
Licensed under the GNU General Public License, version 3 (GPL-3.0)
http://www.opensource.org/licenses/GPL-3.0
Date: Thu May 31 19:00:00 2012 -0400

. Easy to implement.
. Lightweight 2.1Kb
. Special for mobile web apps

Version 1.1:
. Fixed firefox compatibility

Version 1.2:
. Fixed hyperlink normal functionality when transt attribute is not used
. Fixed Error 0 when running locally

Version 1.3:
. Back button bug fixed
. Nav buttons effect
. iOS compatibility fixed

Version v1.4:	
. IE9 bug fixed (however transition effect is not shown)
. data-trans attribute instead of trans
. Parameters
. Transitions for buttons
. Nested elements inside anchor
. CallBack onTransitionFinished

To implement it you just have to reference one css and one js file:

	<link href="css/transition.css" rel="stylesheet" type="text/css"/>
	<script type="text/javascript" src="js/fasw.transitions.min.js"></script>
	<script type="text/javascript">	new ft({}); </script>

and in any link you want the transition just add a “data-ftrans” attribute:
	
	<a data-ftrans="slide" href="slide2.html">Next</a>


- Optional parameters:

.if you want to implement a transition effect for nav button just set the effect in the parameter "navB":
.if you want to implement transitions for button set parameter "but" to true and set <input type="button" data-ftrans="slide" data-href="slide2.html" value="Next">
.you can assign "cba" parameter to a function which will be triggered after a transition is completed.
<script type="text/javascript">
	var params =	//All params are optional, you can just assign {} 
		{ 
			"navB" : "slide reverse",	//Effect for navigation button, leave it empty to disable it
			"but" : true,			//Flag to enable transitions on button, false by default
			"cBa" : function() { }		//callback function
		};
	new ft(params);
</script>



For support go to:
http://www.fasw.ws/faswwp/non-jquery-page-transitions-lightweight
