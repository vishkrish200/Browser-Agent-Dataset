'''
Tests for dataset splitting utilities.
'''
import pytest
# from src.dataset_builder.splitting import DataSplitter # Adjust import
# from src.dataset_builder.types import FormattedEntry # Adjust import

class TestDataSplitter:
    @pytest.fixture
    def sample_data(self):
        return [{"id": str(i), "data": f"item_{i}"} for i in range(100)] # Example FormattedEntry

    def test_split_data_proportions(self, sample_data):
        '''Test splitting data into train, validation, and test sets by proportions.'''
        # splitter = DataSplitter(train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
        # train_set, val_set, test_set = splitter.split(sample_data)
        # assert len(train_set) == 70
        # assert len(val_set) == 15
        # assert len(test_set) == 15
        # # Ensure no overlap and all data is present
        # all_ids = {item['id'] for item in sample_data}
        # train_ids = {item['id'] for item in train_set}
        # val_ids = {item['id'] for item in val_set}
        # test_ids = {item['id'] for item in test_set}
        # assert train_ids.isdisjoint(val_ids)
        # assert train_ids.isdisjoint(test_ids)
        # assert val_ids.isdisjoint(test_ids)
        # assert (train_ids | val_ids | test_ids) == all_ids
        pytest.skip("DataSplitter not yet fully implemented")

    def test_split_data_invalid_proportions(self):
        '''Test splitting with invalid proportions (e.g., sum not equal to 1).'''
        # with pytest.raises(ValueError):
        #     DataSplitter(train_ratio=0.7, val_ratio=0.2, test_ratio=0.2)
        pytest.skip("DataSplitter not yet fully implemented")

    def test_split_data_shuffle(self, sample_data):
        '''Test that shuffling data before splitting results in different splits.'''
        # splitter_no_shuffle = DataSplitter(train_ratio=0.5, val_ratio=0.5, shuffle=False)
        # train1, val1 = splitter_no_shuffle.split(sample_data)
        # 
        # splitter_shuffle = DataSplitter(train_ratio=0.5, val_ratio=0.5, shuffle=True, random_seed=42)
        # train2, val2 = splitter_shuffle.split(sample_data)
        # 
        # # Check they are not identical (highly probable with shuffling)
        # assert train1 != train2
        # assert val1 != val2
        # 
        # # Check that shuffling with the same seed produces the same result
        # splitter_shuffle_seeded_again = DataSplitter(train_ratio=0.5, val_ratio=0.5, shuffle=True, random_seed=42)
        # train3, val3 = splitter_shuffle_seeded_again.split(sample_data)
        # assert train2 == train3
        # assert val2 == val3
        pytest.skip("DataSplitter not yet fully implemented")

# Add more tests for edge cases like small datasets, or only train/test splits. 