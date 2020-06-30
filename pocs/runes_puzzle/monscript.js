var images="images\\";
function creerDamier(x,y) {
	damier={};

	damier.x=x; // x nombre de colonnes
	damier.y=y; //y nombre de lignes
	
	damier.PUZZLE_SUCCESS_STATE = [
    [true, false,false, true],
    [false, false,false, false],
    [false, false,false, false],
    [false, false,false, false]
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

	for (var j = y-1; j >=0; j--) {
		content += "<tr>";
		for (var i = 0; i < x; i++) {
			content += "<td> <img id='"+i+"_"+j+"' height="+size+ "px width="+size+"px src='"+images+"puzzle_cell_"+i+"_"+j+".png'> </td>"; 
		}
		content += "</tr>";
	}
	content += "</table>"
	$('#tble').append(content);

}

function clickEvent(){
	$("img").click(function() {
		var win=false;
	   var imageFront = $(this).attr("src");
	   var myId = $(this).attr("id");
	   
	   $('#'+myId).fadeOut('fast', function () {
	  //puzzle_cell_1_1(_alt).png
	    var	x=parseInt((myId).substr(0,1));
		var y=parseInt((myId).substr(2));
	   	//tester aver current à la place de "alt" match
	   		if ((imageFront).substr(24,3)=="alt"){
		   				
		   				var newImage=images+'puzzle_cell_'+x+'_'+y+'.png';
		   				$('#'+myId).attr("src", newImage);
		   			
	   				
	   		}else{	
	   			if (damier.PUZZLE_SUCCESS_STATE[damier.y-1-y][x]==true) {
	   				if (damier.PUZZLE_CURRENT_STATE[damier.y-1-y][x]==true) {
	   					damier.PUZZLE_CURRENT_STATE[damier.y-1-y][x]=false;
	   					var newImage=images+'puzzle_cell_'+x+'_'+y+'.png';
		   				$('#'+myId).attr("src", newImage);


	   				}else{
		   				damier.PUZZLE_CURRENT_STATE[damier.y-1-y][x]=true;
						$('#'+myId).attr("src", images+'smiley.png');
		   				var snd = new Audio("audios\\chime.mp3"); // buffers automatically when created
			    		snd.play();
			    		if(damier.PUZZLE_CURRENT_STATE.toString()==damier.PUZZLE_SUCCESS_STATE.toString()){
				   		 $("#win").show();
				   		 $("img").off('click');

				   	}
			    	}
	   			}else{
	   				var newImage=images+'puzzle_cell_'+x+'_'+y+'(_alt).png';
	   				$('#'+myId).attr("src", newImage);
	   			}

	   		};
	   	
	   $('#'+myId).fadeIn('fast');
    	}); 
	   		
	   var snd = new Audio("audios\\pi.mp3"); // buffers automatically when created
		snd.play();
		
		
	});

}

$("#win").hide();
damier=creerDamier(4,4);


dessinerDamier(damier);
clickEvent();
