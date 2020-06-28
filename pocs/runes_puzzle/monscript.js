function creerDamier(x,y) {
	damier={};

	damier.x=x; // x nombre de colonnes
	damier.y=y; //y nombre de lignes
	
	damier.PUZZLE_SUCCESS_STATE = [
    [false, false,false, false,false, false,false, false],
    [false, false,false, false,false, false,false, false],
    [false, true,false, false,false, false,true, false],
    [false, false,false, false,false, false,false, false],
    [false, false,false, false,false, false,false, false],
    [false, true,false, false,false, false,true, false],
    [false, false,true, true,true, true,false, false],
    [false, false,false, false,false, false,false, false],
    ];

	damier.PUZZLE_CURRENT_STATE = new Array(y);
	for (var i = 0; i < y; i++){
	 	damier.PUZZLE_CURRENT_STATE[i] = new Array(x);
	 	for (var j = 0; j < x; j++){
	 		damier.PUZZLE_CURRENT_STATE[i][j]=false;
	 	}
	}
	
	return damier;
}

function dessinerDamier(damier) {
	x=damier.x;
	y=damier.y;
	var width = window.innerWidth / (2 * x);
	var height = window.innerHeight / (2 *y);
	var size = Math.min(width, height);
	var content = "<table>";

	for (var i = 0; i < y; i++) {
		content += "<tr>";
		for (var j = 0; j < x; j++) {
			content += "<td> <img id='"+i+"_"+j+"' height="+size+ "px width="+size+"px src='rouge.png'> </td>";
		}
		content += "</tr>";
	}
	content += "</table>"
	$('#tble').append(content);
	

}


function clickEvent(){
	$("img").click(function() {
	   var myId = $(this).attr("id");
	   $('#'+myId).fadeOut('fast', function () {
	  
	    var	y=parseInt((myId).substr(0,1));
		var x=parseInt((myId).substr(2));
	   	if (damier.PUZZLE_SUCCESS_STATE[y][x]==true) {
	   		damier.PUZZLE_CURRENT_STATE[y][x]=true;
	   		$('#'+myId).attr("src", 'noir.png');
	   		var snd = new Audio("audios\\chime.mp3"); // buffers automatically when created
		    snd.play();
	   	}
	   	
	   	if(damier.PUZZLE_SUCCESS_STATE.toString()==damier.PUZZLE_CURRENT_STATE.toString()){
	   		alert("Bravo");
	   	}

	   $('#'+myId).fadeIn('fast');
    	}); 
	   var snd = new Audio("audios\\pi.mp3"); // buffers automatically when created
		snd.play();
		
		
	});

}


damier=creerDamier(8,8);


dessinerDamier(damier);
clickEvent();
