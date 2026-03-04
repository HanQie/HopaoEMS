import unittest
from src.services.db import init_db
from src.services.sample_repo import create_sample, get_sample, list_samples

class TestDbSampleRepo(unittest.TestCase):
    def setUp(self):
        # Re-init DB for fresh state
        init_db()

    def test_create_and_get_sample(self):
        payload = {
            'name': 'Sample Alpha',
            'code': 'SA-001',
            'category': 'Fabric',
            'tags': 'cotton, premium',
            'description': 'High quality cotton sample',
            'image_url': 'http://example.com/alpha.jpg',
            'status': 'active'
        }
        
        # Create
        sample_id = create_sample(payload)
        self.assertIsNotNone(sample_id)
        
        # Get
        sample = get_sample(sample_id)
        self.assertIsNotNone(sample)
        self.assertEqual(sample['name'], 'Sample Alpha')
        self.assertEqual(sample['code'], 'SA-001')
        self.assertEqual(sample['category'], 'Fabric')
        self.assertEqual(sample['image_url'], 'http://example.com/alpha.jpg')

    def test_list_samples(self):
        create_sample({'name': 'S1', 'code': 'C1'})
        create_sample({'name': 'S2', 'code': 'C2'})
        
        samples = list_samples()
        self.assertEqual(len(samples), 2)
        # Repo sorts by ID DESC by default or as implemented
        self.assertEqual(samples[0]['name'], 'S2')
        self.assertEqual(samples[1]['name'], 'S1')

if __name__ == '__main__':
    unittest.main()
