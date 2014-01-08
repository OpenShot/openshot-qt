$(document).ready(function() {
	
	$( "#toggle_debug" ).click(function() {
		$( ".debug-window" ).toggle( 'slide' );
		if ($("#toggle_debug").text() == 'DATA +')
	    {
	    	$("#toggle_debug").text('DATA -');
	    } else {
	    	$("#toggle_debug").text('DATA +');
	    }
	    	
	 });
});