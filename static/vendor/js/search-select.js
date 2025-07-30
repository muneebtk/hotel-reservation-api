document.addEventListener('DOMContentLoaded', function() {
    class SearchBox {
        constructor() {
            this.items = [];
            this.input = document.querySelector('#roomtypes');
            console.log(this.input,"============================")
            this.resultsContainer = document.querySelector('.room-type-results-container');
            
            this.setupEventListeners();
            this.fetchItems();
        }
        
        async fetchItems() {
            try {
                // Replace with orifinal API call
                const response = await new Promise(resolve => 
                    setTimeout(() => resolve({
                        data: ['Apple', 'Banana', 'Orange', 'Mango', 'Pineapple']
                    }), 500)
                );
                this.items = response.data;
            } catch (error) {
                console.error('Error fetching items:', error);
            }
        }

        
        
        async addNewItem(newItem) {
            alert("Enter")
            const csrfToken = document.getElementById('csrf').value;
            try {
                // Perform the API call to add the new item
                const response = await fetch('vendor/room-type-management/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ item: newItem })
                });
        
                // Check if the response is successful
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
        
                const data = await response.json();
                console.log(data,"==============================")
                // Add the new item to the list (assuming the response contains the new item)
                this.items.push(data.item);
        
                // Set the input value to the new item
                this.input.value = data.item;
        
                // Hide results (assumed to be some UI handling)
                this.hideResults();
            } catch (error) {
                console.error('Error adding item:', error);
            }
        }
        
        
        setupEventListeners() {
            this.input.addEventListener('input', () => this.handleSearch());
            this.input.addEventListener('focus', () => this.handleSearch());
            document.addEventListener('click', (e) => {
                if (!this.input.contains(e.target) && !this.resultsContainer.contains(e.target)) {
                    this.hideResults();
                }
            });
        }
        
        handleSearch() {
            const searchTerm = this.input.value.toLowerCase();
            const filteredItems = this.items.filter(item => 
                item.toLowerCase().includes(searchTerm)
            );
            
            this.showResults(filteredItems);
        }
        
        showResults(filteredItems) {
            this.resultsContainer.style.display = 'flex';
            this.resultsContainer.innerHTML = '';
            
            if (filteredItems.length > 0) {
                filteredItems.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'result-item';
                    div.textContent = item;
                    div.onclick = () => {
                        this.input.value = item;
                        this.hideResults();
                    };
                    this.resultsContainer.appendChild(div);
                });
            } else if (this.input.value) {
                const addNew = document.createElement('div');
                addNew.className = 'add-new';
                addNew.innerHTML = `
                    <span>+</span>
                    <span>Add "${this.input.value}"</span>
                `;
                addNew.onclick = () => this.addNewItem(this.input.value);
                this.resultsContainer.appendChild(addNew);
            }
        }
        
        hideResults() {
            this.resultsContainer.style.display = 'none';
        }
    }

    // Initializing the search box
    new SearchBox();
})