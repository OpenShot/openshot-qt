<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<title>jQuery UI jQuery documentation</title>

	<style>
	body {
		font-family: "Trebuchet MS", "Arial", "Helvetica", "Verdana", "sans-serif"
	}
	.gutter {
		display: none;
	}
	</style>
</head>
<body>

<script>{
		"title":
			"Widget Factory",
		"excerpt":
			"Create stateful jQuery plugins using the same abstraction as all jQuery UI widgets.",
		"termSlugs": {
			"category": [
				"utilities","utilities","widgets"
			]
		}
	}</script><div class="toc">
<h4><span>Contents:</span></h4>
<ul class="toc-list">
<li>
<a href="#jQuery-widget1">jQuery.widget( name [, base ], prototype )</a><ul><li>jQuery.widget( name [, base ], prototype )</li></ul>
</li>
<li><a href="#jQuery-Widget2">jQuery.Widget</a></li>
</ul>
</div><article id="jQuery-widget1" class="entry method"><h2 class="section-title"><span class="name">jQuery.widget( name [, base ], prototype )</span></h2>
<div class="entry-wrapper">
<p class="desc"><strong>Description: </strong>Create stateful jQuery plugins using the same abstraction as all jQuery UI widgets.</p>
<ul class="signatures"><li class="signature" id="jQuery-widget-name-base-prototype">
<h4 class="name">jQuery.widget( name [, base ], prototype )</h4>
<ul>
<li>
<div><strong>name</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The name of the widget to create, including the namespace.</div>
</li>
<li>
<div><strong>base</strong></div>
<div>Type: <a href="http://api.jquery.com/Types/#Function">Function</a>()</div>
<div>The base widget to inherit from. This must be a constructor that can be instantiated with the `new` keyword. Defaults to <code>jQuery.Widget</code>.</div>
</li>
<li>
<div><strong>prototype</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#PlainObject">PlainObject</a>
</div>
<div>The object to use as a prototype for the widget.</div>
</li>
</ul>
</li></ul>
<div class="longdesc" id="entry-longdesc">
			<p>You can create new widgets from scratch, using just the <code>$.Widget</code> object as a base to inherit from, or you can explicitly inherit from existing jQuery UI or third-party widgets. Defining a widget with the same name as you inherit from even allows you to extend widgets in place.</p>

			<p>jQuery UI contains many widgets that maintain state and therefore have a slightly different usage pattern than typical jQuery plugins. All of jQuery UI's widgets use the same patterns, which is defined by the widget factory. So if you learn how to use one widget, then you'll know how to use all of them.</p>

			<p><em>Note: This documentation shows examples using the <a href="/progressbar">progressbar widget</a> but the syntax is the same for every widget.</em></p>

			<h3>Initialization</h3>

			<p>In order to track the state of the widget, we must introduce a full life cycle for the widget. The life cycle starts when the widget is initalized. To initialize a widget, we simply call the plugin on one or more elements.</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).progressbar();</code></div></div></td></tr></tbody></table></div>

			<p>This will initialize each element in the jQuery object, in this case the element with an id of <code>"elem"</code>. Because we called the <code>progressbar()</code> method with no parameters, the widget is initialized with its default options. We can pass a set of options during initialization in order to override the default options.</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).progressbar({ value: 20 });</code></div></div></td></tr></tbody></table></div>

			<p>We can pass as many or as few options as we want during initialization. Any options that we don't pass will just use their default values.</p>

			<p>The options are part of the widget's state, so we can set options after initialization as well. We'll see this later with the option method.</p>

			<h3>Methods</h3>

			<p>Now that the widget is initialized, we can query its state or perform actions on the widget. All actions after initialization take the form of a method call. To call a method on a widget, we pass the name of the method to the jQuery plugin. For example, to call the <code>value()</code> method on our progressbar widget, we would use:</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).progressbar( </code><code class="string">"value"</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>

			<p>If the method accepts parameters, we can pass them after the method name. For example, to pass the parameter <code>40</code> to the <code>value()</code> method, we can use:</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).progressbar( </code><code class="string">"value"</code><code class="plain">, 40 );</code></div></div></td></tr></tbody></table></div>

			<p>Just like other methods in jQuery, most widget methods return the jQuery object for chaining.</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">)</code></div><div class="line number2 index1 alt1"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">.progressbar( </code><code class="string">"value"</code><code class="plain">, 90 )</code></div><div class="line number3 index2 alt2"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">.addClass( </code><code class="string">"almost-done"</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>

			<p>Each widget will have its own set of methods based on the functionality that the widget provides. However, there are a few methods that exist on all widgets, which are documented below.</p>

			<h3>Events</h3>

			<p>All widgets have events associated with their various behaviors to notify you when the state is changing. For most widgets, when the events are triggered, the names are prefixed with the widget name. For example, we can bind to progressbar's <code>change</code> event which is triggered whenever the value changes.</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).bind( </code><code class="string">"progressbarchange"</code><code class="plain">, </code><code class="keyword">function</code><code class="plain">() {</code></div><div class="line number2 index1 alt1"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">alert( </code><code class="string">"The value has changed!"</code> <code class="plain">);</code></div><div class="line number3 index2 alt2"><code class="plain">});</code></div></div></td></tr></tbody></table></div>

			<p>Each event has a corresponding callback, which is exposed as an option. We can hook into progressbar's <code>change</code> callback instead of binding to the <code>progressbarchange</code> event, if we want to.</p>

			<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">"#elem"</code> <code class="plain">).progressbar({</code></div><div class="line number2 index1 alt1"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">change: </code><code class="keyword">function</code><code class="plain">() {</code></div><div class="line number3 index2 alt2"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">alert( </code><code class="string">"The value has changed!"</code> <code class="plain">);</code></div><div class="line number4 index3 alt1"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">}</code></div><div class="line number5 index4 alt2"><code class="plain">});</code></div></div></td></tr></tbody></table></div>

			<p>All widgets have a <code>create</code> event which is triggered upon instantiation.</p>
		</div>
</div></article><article id="jQuery-Widget2" class="entry widget"><h2 class="section-title"><span>Base Widget</span></h2>
<div class="entry-wrapper">
<p class="desc"><strong>Description: </strong>The base widget used by the widget factory.</p>
<section id="quick-nav"><header><h2>QuickNav</h2></header><div class="quick-nav-section">
<h3>Options</h3>
<div><a href="#option-disabled">disabled</a></div>
<div><a href="#option-hide">hide</a></div>
<div><a href="#option-show">show</a></div>
</div>
<div class="quick-nav-section">
<h3>Methods</h3>
<div><a href="#method-destroy">destroy</a></div>
<div><a href="#method-disable">disable</a></div>
<div><a href="#method-enable">enable</a></div>
<div><a href="#method-option">option</a></div>
<div><a href="#method-widget">widget</a></div>
<div><a href="#method-_create">_create</a></div>
<div><a href="#method-_destroy">_destroy</a></div>
<div><a href="#method-_getCreateEventData">_getCreateEventData</a></div>
<div><a href="#method-_getCreateOptions">_getCreateOptions</a></div>
<div><a href="#method-_init">_init</a></div>
<div><a href="#method-_setOptions">_setOptions</a></div>
<div><a href="#method-_setOption">_setOption</a></div>
<div><a href="#method-_on">_on</a></div>
<div><a href="#method-_off">_off</a></div>
<div><a href="#method-_super">_super</a></div>
<div><a href="#method-_superApply">_superApply</a></div>
<div><a href="#method-_delay">_delay</a></div>
<div><a href="#method-_hoverable">_hoverable</a></div>
<div><a href="#method-_focusable">_focusable</a></div>
<div><a href="#method-_trigger">_trigger</a></div>
<div><a href="#method-_show">_show</a></div>
<div><a href="#method-_hide">_hide</a></div>
</div>
<div class="quick-nav-section">
<h3>Events</h3>
<div><a href="#event-create">create</a></div>
</div></section><section id="options"><header><h2 class="underline">Options</h2></header><div id="option-disabled" class="api-item first-item">
<h3>disabled<span class="option-type"><strong>Type: </strong><a href="http://api.jquery.com/Types#Boolean">Boolean</a></span>
</h3>
<div class="default">
<strong>Default: </strong><code>false</code>
</div>
<div>Disables the jQuery.Widget if set to <code>true</code>.</div>
<strong>Code examples:</strong><p>Initialize the jQuery.Widget with the disabled option specified:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget({ disabled: </code><code class="keyword">true</code> <code class="plain">});</code></div></div></td></tr></tbody></table></div>
<p>Get or set the disabled option, after initialization:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="comments">// getter</code></div><div class="line number2 index1 alt1"><code class="keyword">var</code> <code class="plain">disabled = $( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"disabled"</code> <code class="plain">);</code></div><div class="line number3 index2 alt2">&nbsp;</div><div class="line number4 index3 alt1"><code class="comments">// setter</code></div><div class="line number5 index4 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"disabled"</code><code class="plain">, </code><code class="keyword">true</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>
</div>
<div id="option-hide" class="api-item">
<h3>hide<span class="option-type"><strong>Type: </strong><a href="http://api.jquery.com/Types#Boolean">Boolean</a> or <a href="http://api.jquery.com/Types#Number">Number</a> or <a href="http://api.jquery.com/Types#String">String</a> or <a href="http://api.jquery.com/Types#Object">Object</a></span>
</h3>
<div class="default">
<strong>Default: </strong><code>null</code>
</div>
<div>If and how to animate the hiding of the element.</div>
<strong>Multiple types supported:</strong><ul>
<li>
<strong>Boolean</strong>: 
			When set to <code>false</code>, no animation will be used and the element will be hidden immediately.
			When set to <code>true</code>, the element will fade out with the default duration and the default easing.
		</li>
<li>
<strong>Number</strong>: 
			The element will fade out with the specified duration and the default easing.
		</li>
<li>
<strong>String</strong>: 
			The element will be hidden using the specified effect.
			The value can either be the name of a built-in jQuery animateion method, such as <code>"slideUp"</code>, or the name of a jQuery UI effect, such as <code>"fold"</code>.
			In either case the effect will be used with the default duration and the default easing.
		</li>
<li>
<strong>Object</strong>: If the value is an object, then <code>effect</code>, <code>duration</code>, and <code>easing</code> properties may be provided. If the <code>effect</code> property contains the name of a jQuery method, then that method will be used; otherwise it is assumed to be the name of a jQuery UI effect. When using a jQuery UI effect that supports additional settings, you may include those settings in the object and they will be passed to the effect. If <code>duration</code> or <code>easing</code> is omitted, then the default values will be used. If <code>effect</code> is omitted, then <code>"fadeOut"</code> will be used.</li>
</ul>
<strong>Code examples:</strong><p>Initialize the jQuery.Widget with the hide option specified:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget({ hide: { effect: </code><code class="string">"explode"</code><code class="plain">, duration: 1000 } });</code></div></div></td></tr></tbody></table></div>
<p>Get or set the hide option, after initialization:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="comments">// getter</code></div><div class="line number2 index1 alt1"><code class="keyword">var</code> <code class="plain">hide = $( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"hide"</code> <code class="plain">);</code></div><div class="line number3 index2 alt2">&nbsp;</div><div class="line number4 index3 alt1"><code class="comments">// setter</code></div><div class="line number5 index4 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"hide"</code><code class="plain">, { effect: </code><code class="string">"explode"</code><code class="plain">, duration: 1000 } );</code></div></div></td></tr></tbody></table></div>
</div>
<div id="option-show" class="api-item">
<h3>show<span class="option-type"><strong>Type: </strong><a href="http://api.jquery.com/Types#Boolean">Boolean</a> or <a href="http://api.jquery.com/Types#Number">Number</a> or <a href="http://api.jquery.com/Types#String">String</a> or <a href="http://api.jquery.com/Types#Object">Object</a></span>
</h3>
<div class="default">
<strong>Default: </strong><code>null</code>
</div>
<div>If and how to animate the showing of the element.</div>
<strong>Multiple types supported:</strong><ul>
<li>
<strong>Boolean</strong>: 
			When set to <code>false</code>, no animation will be used and the element will be shown immediately.
			When set to <code>true</code>, the element will fade in with the default duration and the default easing.
		</li>
<li>
<strong>Number</strong>: 
			The element will fade in with the specified duration and the default easing.
		</li>
<li>
<strong>String</strong>: 
			The element will be shown using the specified effect.
			The value can either be the name of a built-in jQuery animateion method, such as <code>"slideDown"</code>, or the name of a jQuery UI effect, such as <code>"fold"</code>.
			In either case the effect will be used with the default duration and the default easing.
		</li>
<li>
<strong>Object</strong>: If the value is an object, then <code>effect</code>, <code>duration</code>, and <code>easing</code> properties may be provided. If the <code>effect</code> property contains the name of a jQuery method, then that method will be used; otherwise it is assumed to be the name of a jQuery UI effect. When using a jQuery UI effect that supports additional settings, you may include those settings in the object and they will be passed to the effect. If <code>duration</code> or <code>easing</code> is omitted, then the default values will be used. If <code>effect</code> is omitted, then <code>"fadeIn"</code> will be used.</li>
</ul>
<strong>Code examples:</strong><p>Initialize the jQuery.Widget with the show option specified:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget({ show: { effect: </code><code class="string">"blind"</code><code class="plain">, duration: 800 } });</code></div></div></td></tr></tbody></table></div>
<p>Get or set the show option, after initialization:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="comments">// getter</code></div><div class="line number2 index1 alt1"><code class="keyword">var</code> <code class="plain">show = $( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"show"</code> <code class="plain">);</code></div><div class="line number3 index2 alt2">&nbsp;</div><div class="line number4 index3 alt1"><code class="comments">// setter</code></div><div class="line number5 index4 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"show"</code><code class="plain">, { effect: </code><code class="string">"blind"</code><code class="plain">, duration: 800 } );</code></div></div></td></tr></tbody></table></div>
</div></section><section id="methods"><header><h2 class="underline">Methods</h2></header><div id="method-_create"><div class="api-item first-item">
<h3>_create()</h3>
<div>
					The <code>_create()</code> method is the widget's constructor.
					There are no parameters, but <code>this.element</code> and <code>this.options</code> are already set.
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_delay"><div class="api-item">
<h3>_delay( fn [, delay ] )<span class="returns">Returns: <a href="http://api.jquery.com/Types#Number">Number</a></span>
</h3>
<div>
					Invokes the provided function after a specified delay. Keeps <code>this</code> context correct. Essentially <code>setTimeout()</code>.
					<p>Returns the timeout ID for use with <code>clearTimeout()</code>.</p>
				</div>
<ul>
<li>
<div><strong>fn</strong></div>
<div>Type: <a href="http://api.jquery.com/Types/#Function">Function</a>() or <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The function to invoke. Can also be the name of a method on the widget.</div>
</li>
<li>
<div><strong>delay</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Number">Number</a>
</div>
<div>The number of milliseconds to wait before invoking the function. Deafults to <code>0</code>.</div>
</li>
</ul>
</div></div>
<div id="method-_destroy"><div class="api-item">
<h3>_destroy()</h3>
<div>
					The public <a href="#method-destroy"><code>destroy()</code></a> method cleans up all common data, events, etc. and then delegates out to <code>_destroy()</code> for custom, widget-specific, cleanup.
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_focusable"><div class="api-item">
<h3>_focusable( element )</h3>
<div>
					Sets up <code>element</code> to apply the <code>ui-state-focus</code> class on focus.
					<p>The event handlers are automatically cleaned up on destroy.</p>
				</div>
<ul><li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>The element(s) to apply the focusable behavior to.</div>
</li></ul>
</div></div>
<div id="method-_getCreateEventData"><div class="api-item">
<h3>_getCreateEventData()<span class="returns">Returns: <a href="http://api.jquery.com/Types#Object">Object</a></span>
</h3>
<div>
					All widgets trigger the <a href="#event-create"><code>create</code></a> event. By default, no data is provided in the event, but this method can return an object which will be passed as the <code>create</code> event's data.
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_getCreateOptions"><div class="api-item">
<h3>_getCreateOptions()<span class="returns">Returns: <a href="http://api.jquery.com/Types#Object">Object</a></span>
</h3>
<div>
					This method allows the widget to define a custom method for defining options during instantiation. This user-provided options override the options returned by this method which override the default options.
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_hide"><div class="api-item">
<h3>_hide( element, option [, callback ] )</h3>
<div>
					Hides an element immediately, using built-in animation methods, or using custom effects.
					See the <a href="#option-hide">hide</a> option for possible <code>option</code> values.
				</div>
<ul>
<li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>The element(s) to hide.</div>
</li>
<li>
<div><strong>option</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>The settings defining how to hide the element.</div>
</li>
<li>
<div><strong>callback</strong></div>
<div>Type: <a href="http://api.jquery.com/Types/#Function">Function</a>()</div>
<div>Callback to invoke after the element has been fully hidden.</div>
</li>
</ul>
</div></div>
<div id="method-_hoverable"><div class="api-item">
<h3>_hoverable( element )</h3>
<div>
					Sets up <code>element</code> to apply the <code>ui-state-hover</code> class on hover.
					<p>The event handlers are automatically cleaned up on destroy.</p>
				</div>
<ul><li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>The element(s) to apply the hoverable behavior to.</div>
</li></ul>
</div></div>
<div id="method-_init"><div class="api-item">
<h3>_init()</h3>
<div>
					Widgets have the concept of initialization that is distinct from creation. Any time the plugin is called with no arguments or with only an option hash, the widget is initialized; this includes when the widget is created.

					<p><em>Note: Initialization should only be handled if there is a logical action to perform on successive calls to the widget with no arguments.</em></p>
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_off"><div class="api-item">
<h3>_off( element, eventName )</h3>
<div>
					Unbinds event handlers from the specified element(s).
				</div>
<ul>
<li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>
						The element(s) to unbind the event handlers from. Unlike the <code>_on()</code> method, the elements are required for <code>_off()</code>.
					</div>
</li>
<li>
<div><strong>eventName</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>One or more space-separated event types.</div>
</li>
</ul>
</div></div>
<div id="method-_on"><div class="api-item">
<h3>_on(  [element ], handlers )</h3>
<div>
					Binds event handlers to the specified element(s). Delegation is supported via selectors inside the event names, e.g., "<code>click .foo</code>". The <code>_on()</code> method provides several benefits of direct event binding:
					<ul>
						<li>Maintains proper <code>this</code> context inside the handlers.</li>
						<li>Automatically handles disabled widgets: If the widget is disabled or the event occurs on an element with the <code>ui-state-disabled</code> class, the event handler is not invoked.</li>
						<li>Event handlers are automatically namespaced and cleaned up on destroy.</li>
					</ul>
				</div>
<ul>
<li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>Which element(s) to bind the event handlers to. If no element is provided, <code>this.element</code> is used.</div>
</li>
<li>
<div><strong>handlers</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>
						A map in which the string keys represent the event type and optional selector for delegation, and the values represent a handler function to be called for the event.
					</div>
</li>
</ul>
</div></div>
<div id="method-_setOption"><div class="api-item">
<h3>_setOption( key, value )</h3>
<div>
					Called from the <a href="#method-_setOptions"><code>_setOptions()</code></a> method for each individual option. Widget state should be updated based on changes.
				</div>
<ul>
<li>
<div><strong>key</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The name of the option to set.</div>
</li>
<li>
<div><strong>value</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>A value to set for the option.</div>
</li>
</ul>
</div></div>
<div id="method-_setOptions"><div class="api-item">
<h3>_setOptions( options )</h3>
<div>
					Called whenever the <a href="#method-option"><code>option()</code></a> method is called, regardless of the form in which the <code>option()</code> method was called.
					<p>Overriding this is useful if you can defer processor-intensive changes for multiple option changes.</p>
				</div>
<ul><li>
<div><strong>options</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>A map of option-value pairs to set.</div>
</li></ul>
</div></div>
<div id="method-_show"><div class="api-item">
<h3>_show( element, option [, callback ] )</h3>
<div>
					Shows an element immediately, using built-in animation methods, or using custom effects.
					See the <a href="#option-show">show</a> option for possible <code>option</code> values.
				</div>
<ul>
<li>
<div><strong>element</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#jQuery">jQuery</a>
</div>
<div>The element(s) to show.</div>
</li>
<li>
<div><strong>option</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>The settings defining how to show the element.</div>
</li>
<li>
<div><strong>callback</strong></div>
<div>Type: <a href="http://api.jquery.com/Types/#Function">Function</a>()</div>
<div>Callback to invoke after the element has been fully shown.</div>
</li>
</ul>
</div></div>
<div id="method-_super"><div class="api-item">
<h3>_super()</h3>
<div>
					Invokes the method of the same name from the parent widget, with any specified arguments. Essentially <code>.call()</code>.
				</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-_superApply"><div class="api-item">
<h3>_superApply( arguments )</h3>
<div>
					Invokes the method of the same name from the parent widget, with the array of arguments. Essentially <code>.apply()</code>.
				</div>
<ul><li>
<div><strong>arguments</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Array">Array</a>
</div>
<div>Array of arguments to pass to the parent method.</div>
</li></ul>
</div></div>
<div id="method-_trigger"><div class="api-item">
<h3>_trigger( type [, event ] [, data ] )</h3>
<div>
					Triggers an event and its associated callback.
					<p>The option with the name equal to type is invoked as the callback.</p>
					<p>The event name is the widget name + type.</p>
					<p><em>Note: When providing data, you must provide all three parameters. If there is no event to pass along, just pass <code>null</code>.</em></p>
				</div>
<ul>
<li>
<div><strong>type</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The <code>type</code> should match the name of a callback option. The full event type will be generated automatically.</div>
</li>
<li>
<div><strong>event</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Event">Event</a>
</div>
<div>The original event that caused this event to occur; useful for providing context to the listener.</div>
</li>
<li>
<div><strong>data</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>A hash of data associated with the event.</div>
</li>
</ul>
</div></div>
<div id="method-destroy"><div class="api-item">
<h3>destroy()</h3>
<div>
		Removes the jQuery.Widget functionality completely. This will return the element back to its pre-init state.
	</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-disable"><div class="api-item">
<h3>disable()</h3>
<div>
		Disables the jQuery.Widget.
	</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-enable"><div class="api-item">
<h3>enable()</h3>
<div>
		Enables the jQuery.Widget.
	</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div>
<div id="method-option">
<div class="api-item">
<h3>option( optionName )<span class="returns">Returns: <a href="http://api.jquery.com/Types#Object">Object</a></span>
</h3>
<div>Gets the value currently associated with the specified <code>optionName</code>.</div>
<ul><li>
<div><strong>optionName</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The name of the option to get.</div>
</li></ul>
<div>
<strong>Code examples:</strong><p>Invoke the  method:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="keyword">var</code> <code class="plain">isDisabled = $( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"disabled"</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>
</div>
</div>
<div class="api-item">
<h3>option()<span class="returns">Returns: <a href="http://api.jquery.com/Types#PlainObject">PlainObject</a></span>
</h3>
<div>Gets an object containing key/value pairs representing the current jQuery.Widget options hash.</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
<div>
<strong>Code examples:</strong><p>Invoke the  method:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="keyword">var</code> <code class="plain">options = $( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>
</div>
</div>
<div class="api-item">
<h3>option( optionName, value )</h3>
<div>Sets the value of the jQuery.Widget option associated with the specified <code>optionName</code>.</div>
<ul>
<li>
<div><strong>optionName</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#String">String</a>
</div>
<div>The name of the option to set.</div>
</li>
<li>
<div><strong>value</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>A value to set for the option.</div>
</li>
</ul>
<div>
<strong>Code examples:</strong><p>Invoke the  method:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, </code><code class="string">"disabled"</code><code class="plain">, </code><code class="keyword">true</code> <code class="plain">);</code></div></div></td></tr></tbody></table></div>
</div>
</div>
<div class="api-item">
<h3>option( options )</h3>
<div>Sets one or more options for the jQuery.Widget.</div>
<ul><li>
<div><strong>options</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div>A map of option-value pairs to set.</div>
</li></ul>
<div>
<strong>Code examples:</strong><p>Invoke the  method:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget( </code><code class="string">"option"</code><code class="plain">, { disabled: </code><code class="keyword">true</code> <code class="plain">} );</code></div></div></td></tr></tbody></table></div>
</div>
</div>
</div>
<div id="method-widget"><div class="api-item">
<h3>widget()<span class="returns">Returns: <a href="http://api.jquery.com/Types#jQuery">jQuery</a></span>
</h3>
<div>
		Returns a <code>jQuery</code> object containing the original element or other relevant generated element.
	</div>
<ul><li><div class="null-signature">This method does not accept any arguments.</div></li></ul>
</div></div></section><section id="events"><header><h2 class="underline">Events</h2></header><div id="event-create" class="api-item first-item">
<h3>create( event, ui )<span class="returns">Type: <code>jQuery.Widgetcreate</code></span>
</h3>
<div>
		Triggered when the jQuery.Widget is created.
	</div>
<ul>
<li>
<div><strong>event</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Event">Event</a>
</div>
<div></div>
</li>
<li>
<div><strong>ui</strong></div>
<div>Type: <a href="http://api.jquery.com/Types#Object">Object</a>
</div>
<div></div>
</li>
</ul>
<div>
<strong>Code examples:</strong><p>Initialize the jQuery.Widget with the create callback specified:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).jQuery.Widget({</code></div><div class="line number2 index1 alt1"><code class="undefined spaces">&nbsp;&nbsp;&nbsp;&nbsp;</code><code class="plain">create: </code><code class="keyword">function</code><code class="plain">( event, ui ) {}</code></div><div class="line number3 index2 alt2"><code class="plain">});</code></div></div></td></tr></tbody></table></div>
<p>Bind an event listener to the jQuery.Widgetcreate event:</p>
<div class="syntaxhighlighter nogutter  "><table border="0" cellpadding="0" cellspacing="0"><tbody><tr><td class="code"><div class="container"><div class="line number1 index0 alt2"><code class="plain">$( </code><code class="string">".selector"</code> <code class="plain">).on( </code><code class="string">"jQuery.Widgetcreate"</code><code class="plain">, </code><code class="keyword">function</code><code class="plain">( event, ui ) {} );</code></div></div></td></tr></tbody></table></div>
</div>
</div></section>
</div></article>

</body>
</html>
