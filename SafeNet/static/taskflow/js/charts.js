var ctx = document.getElementById('projectChart').getContext('2d');
var projectChart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ['Project 1', 'Project 2', 'Project 3'],
        datasets: [{
            label: 'Progress (%)',
            data: [80, 45, 60],
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});
