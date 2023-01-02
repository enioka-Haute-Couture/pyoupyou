// https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/File_drag_and_drop
function dropHandler(ev) {
    // Prevent default behavior (Prevent file from being opened)
    ev.preventDefault();

    if (ev.dataTransfer.items) {
        // Use DataTransferItemList interface to access the file(s)
        [...ev.dataTransfer.items].forEach((item, i) => {
            // If dropped items aren't files, reject them
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

function dragOverHandler(ev) {
    // Prevent default behavior (Prevent file from being opened)
    ev.preventDefault();
}

// https://stackoverflow.com/questions/5632629/how-to-change-a-file-inputs-filelist-programmatically
function getFiles(input){
    const files = new Array(input.files.length)
    for(let i = 0; i < input.files.length; i++) {
        files[i] = input.files.item(i)
    }
    return files
}

function setFiles(input, files){
    const dataTransfer = new DataTransfer()
    for(const file of files)
        dataTransfer.items.add(file)
    input.files = dataTransfer.files
}

function addFileToList(file, filename) {

    // https://www.w3schools.com/howto/howto_js_close_list_items.asp
    let li = document.createElement("li")
    li.setAttribute("class", "file-li")
    li.innerHTML = file.name
    let cross = document.createElement("span")
    cross.innerHTML = "x"
    cross.setAttribute("class", "close")

    cross.addEventListener("click", (event) => {
        event.preventDefault()
        for (let i = 0; i < curr_files.length; i++) {
            if (curr_files[i].name === filename) {
                curr_files.splice(i, 1)
            }
        }
        event.target.parentElement.remove()
        setFiles(document.getElementById("input-btn-id"), curr_files)
    })

    li.appendChild(cross)
    document.getElementById("file-list-id").appendChild(li)
    curr_files.push(file)
    setFiles(document.getElementById("input-btn-id"), curr_files)
}

let curr_files = []

//TODO: translations
document.getElementById("input-btn-id").addEventListener("change", () => {
    for (const file of getFiles(document.getElementById("input-btn-id"))) {
        addFileToList(file, file.name)
    }
}, false)
