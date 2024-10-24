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

    const doctypes = JSON.parse(document.getElementById('doctypes').textContent);
    let select = document.createElement("select")

    for (const doctype of doctypes){
    let docTypeOption = document.createElement("option")
    docTypeOption.value = doctype
    docTypeOption.textContent = doctype
    docTypeOption.setAttribute("class", "drop-down-menu")
    select.appendChild(docTypeOption)
    };

    select.setAttribute("class", "file-type-select")
    select.setAttribute("name", "doctypes");  // Add the 'name' attribute for form submission
    
    let li = document.createElement("li")
    li.setAttribute("class", "file-li")
    li.textContent = file.name

    li.appendChild(select)  // Append the dropdown to the list item
    li.appendChild(cross)   // Append the close (remove) button
    document.getElementById("file-list-id").appendChild(li)

    curr_files.push(file)
    setFiles(document.getElementById("input-btn-id"), curr_files)
}

let curr_files = []

document.getElementById("input-btn-id").addEventListener("change", () => {
    for (const file of Array.from(document.getElementById("input-btn-id").files)) {
        addFileToList(file, file.name)
    }
}, false)
