
let FLAGS = {}

let FLAG_NAMES = []


fetch("http://127.0.0.1:5000/flags")

.then(r=>r.json())

.then(data=>{

FLAGS = data

FLAG_NAMES = Object.keys(data)

render("")

})


function render(q){

let div = document.getElementById("results")

div.innerHTML = ""

let ql = q.toLowerCase()

let count = 0


for(let i=0;i<FLAG_NAMES.length;i++){

let name = FLAG_NAMES[i]

if(name.toLowerCase().includes(ql)){

let el = document.createElement("div")

el.className = "flag"

el.innerHTML = `

${name}

<input id="v_${name}" placeholder="value">

<button onclick="setflag('${name}')">set</button>

`

div.appendChild(el)

count++

if(count>=120000) break

}

}

}


document

.getElementById("search")

.oninput = e=>render(e.target.value)



function inject(){

fetch(

"http://127.0.0.1:5000/inject",

{method:"POST"}

)

}


function setflag(name){

let val = document.getElementById("v_"+name).value

fetch(

"http://127.0.0.1:5000/setflag",

{

method:"POST",

headers:{

"Content-Type":"application/json"

},

body:JSON.stringify({

flag:name,

value:val

})

}

)

}
