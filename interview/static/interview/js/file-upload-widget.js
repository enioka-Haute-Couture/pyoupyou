// https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API

document.addEventListener('dragover', function(ev) {
    ev.preventDefault();  // must handle dragover event to catch 'drop' event
});

document.addEventListener('drop', function(ev) {
    ev.preventDefault();
    dropHandler(ev);
});

function dropHandler(ev) {

    if (ev.dataTransfer.items) {
        // Use DataTransferItemList interface to access the file(s)
        [...ev.dataTransfer.items].forEach((item, i) => {
            if (item.kind === 'file') {
                const file = item.getAsFile();
                addFileToList(file, file.name)
            }
        });
    } else {
        // Use DataTransfer interface to access the file(s)
        [...ev.dataTransfer.files].forEach((file, i) => {
            addFileToList(file, file.name)
        });
    }
}

function setFiles(input, files){
    const dataTransfer = new DataTransfer()
    for(const file of files)
        dataTransfer.items.add(file)
    input.files = dataTransfer.files
}

// https://www.w3schools.com/howto/howto_js_close_list_items.asp
function addFileToList(file, filename) {

    let cross = document.createElement("span")
    cross.textContent = "x"
    cross.setAttribute("class", "close")

    cross.addEventListener("click", (event) => {
        event.preventDefault();
        curr_files = curr_files.filter(file => file.name !== filename)
        event.target.parentElement.remove()
        setFiles(document.getElementById("input-btn-id"), curr_files)
    });


    let li = document.createElement("li")
    li.setAttribute("class", "file-li")
    li.textContent = file.name

    li.appendChild(cross)
    document.getElementById("file-list-id").appendChild(li)
    curr_files.push(file)
    setFiles(document.getElementById("input-btn-id"), curr_files)
}

let curr_files = []

//TODO: translations
document.getElementById("input-btn-id").addEventListener("change", () => {
    for (const file of Array.from(document.getElementById("input-btn-id").files)) {
        addFileToList(file, file.name)
    }
}, false)
