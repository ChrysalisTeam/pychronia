
// VARIABLE enigmaRunesPuzzleAssetsRoot must be GLOBALLY defined //
var enigmaRunesPuzzleImgRoot = enigmaRunesPuzzleAssetsRoot+"imgs/";
var enigmaRunesPuzzleSndRoot = enigmaRunesPuzzleAssetsRoot+"snds/";

function createPuzzle() {
	damier={};

	damier.PUZZLE_SUCCESS_STATE = [
    [true,true,true],
    [false,true,false],
    [false,true,false]
    ];

	damier.PUZZLE_CURRENT_STATE = new Array(damier.PUZZLE_SUCCESS_STATE.length);
	for (var i = 0; i < damier.PUZZLE_SUCCESS_STATE.length; i++){
	 	damier.PUZZLE_CURRENT_STATE[i] = new Array(damier.PUZZLE_SUCCESS_STATE[i].length);
	 	for (var j = 0; j < damier.PUZZLE_SUCCESS_STATE[i].length; j++){
	 		damier.PUZZLE_CURRENT_STATE[i][j]=false;
	 	}
	}


	return damier;
}

function drawCheckerboard(damier) {
	lengthColumn=new Array();
	for (var i = 0; i < damier.PUZZLE_SUCCESS_STATE.length; i++) {
		lengthColumn[i]=damier.PUZZLE_SUCCESS_STATE[i].length;
	}
	x=Math.max(...lengthColumn);

	y=damier.PUZZLE_SUCCESS_STATE.length;

	var size = $('#enigma-container').width() / x;
	//var height = $('#enigma-container').height() / y;
	//console.log("WIDTH", width, height);
	//var size = Math.min(width, height);
	var content = "<table>";

	for (var j = 0; j<y; j++) {
		content += "<tr>";
		for (var i = 0; i < damier.PUZZLE_SUCCESS_STATE[j].length; i++) {
			content += "<td> <img class=\"rune\" id='"+i+"_"+(damier.PUZZLE_SUCCESS_STATE.length-j-1)+"' height="+size+ "px width="+size+"px src='"+enigmaRunesPuzzleImgRoot+"puzzle_cell_"+i+"_"+(damier.PUZZLE_SUCCESS_STATE.length-j-1)+".png'> </td>";
		}
		content += "</tr>";
	}
	content += "</table>"
	$('#enigma-container').append(content);

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

		   	// Turn the image to the back
		   	if (damier.PUZZLE_CURRENT_STATE[damier.PUZZLE_SUCCESS_STATE.length-1-y][x]==false){
		   		damier.PUZZLE_CURRENT_STATE[damier.PUZZLE_SUCCESS_STATE.length-1-y][x] = true;
		   		var newImage=enigmaRunesPuzzleImgRoot+'puzzle_cell_'+x+'_'+y+'_alt.png';
		   		$('#'+myId).attr("src", newImage);
		   	}
		   	else{
		   		damier.PUZZLE_CURRENT_STATE[damier.PUZZLE_SUCCESS_STATE.length-1-y][x]=false;
				var newImage=enigmaRunesPuzzleImgRoot+'puzzle_cell_'+x+'_'+y+'.png';
				$('#'+myId).attr("src", newImage);
		   	}

			if(damier.PUZZLE_CURRENT_STATE.toString()==damier.PUZZLE_SUCCESS_STATE.toString()){
				$("#victory-overlay").css("display", "block");
				var snd = new Audio(enigmaRunesPuzzleSndRoot + "victory.mp3"); // buffers automatically when created
				snd.play();
				$("img").off('click');
			}


	   $('#'+myId).fadeIn('fast');
    	});

	   var snd = new Audio(enigmaRunesPuzzleSndRoot + "swap.mp3"); // buffers automatically when created
		snd.play();

	});

}

function resetEnigmaRunesPuzzle(){
	$("table").remove();
	$("#victory-overlay").css("display", "none");
	damier=createPuzzle();
	drawCheckerboard(damier);
	clickEvent();
}

function launchEnigmaRunesPuzzle(){
	damier=createPuzzle();
	drawCheckerboard(damier);
	clickEvent();
}

$(launchEnigmaRunesPuzzle);
